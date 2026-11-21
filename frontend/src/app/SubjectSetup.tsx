import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type { DocumentView, SubjectView } from '../api/types'
import { DocumentReview } from '../dashboard/DocumentReview'
import { CourseText } from '../lib/math'

/** A new student's first step (docs/plan/20): name a subject, import its PDFs, and check each one
 * next to the original before Lodestar uses it. The left side is the list; the right side shows
 * the whole selected document, like a side panel, with what Lodestar read from it. */

const STATUS: Record<string, string> = {
  processing: 'Reading…',
  review: 'Ready to check',
  ready: 'Validated',
  failed: 'Could not read',
}

function statusText(doc: DocumentView): string {
  if (doc.status === 'processing' && doc.progress > 0)
    return `Reading page ${String(doc.progress)} of ${String(doc.pages)}`
  return STATUS[doc.status] ?? doc.status
}

function Preview({
  doc,
  onApproved,
  onReview,
}: {
  doc: DocumentView
  onApproved: (doc: DocumentView) => void
  onReview: () => void
}) {
  const [pdf, setPdf] = useState('')
  const [tab, setTab] = useState<'original' | 'read'>('original')
  const [pages, setPages] = useState<{ page: number; text: string; warnings: string[] }[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    let url = ''
    api.documentOriginal(doc.doc_id).then(
      (blob) => {
        if (!active) return
        url = URL.createObjectURL(blob)
        setPdf(url)
      },
      () => {
        if (active) setTab('read')
      },
    )
    return () => {
      active = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [doc.doc_id])

  useEffect(() => {
    if (doc.status !== 'review' && doc.status !== 'ready') return
    let active = true
    api.documentPages(doc.doc_id).then(
      (p) => {
        if (active) setPages(p)
      },
      () => undefined,
    )
    return () => {
      active = false
    }
  }, [doc.doc_id, doc.status])

  const flagged = pages.filter((p) => p.warnings.length > 0 || p.text.includes('[unclear]'))
  const unclear = pages.some((p) => p.text.includes('[unclear]'))

  return (
    <aside className="setup-preview" aria-label={`Preview of ${doc.title}`}>
      <header className="setup-preview__head">
        <div>
          <p className="eyebrow">{statusText(doc)}</p>
          <h2>{doc.title}</h2>
          <p className="muted small">
            {doc.filename} · {doc.pages} pages
            {doc.extraction_method !== 'text' ? ' · read with OCR' : ''}
          </p>
        </div>
        <div className="setup-preview__tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'original'}
            disabled={!pdf}
            onClick={() => {
              setTab('original')
            }}
          >
            Original
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'read'}
            disabled={!pages.length}
            onClick={() => {
              setTab('read')
            }}
          >
            What Lodestar read
          </button>
        </div>
      </header>
      <div className="setup-preview__body">
        {tab === 'original' && pdf && (
          <iframe title={`Original of ${doc.title}`} src={pdf} data-testid="setup-pdf" />
        )}
        {tab === 'original' && !pdf && <p className="muted">Loading the document…</p>}
        {tab === 'read' && (
          <div className="setup-preview__pages">
            {pages.map((p) => (
              <section key={p.page} className="setup-page">
                <p className="eyebrow">Page {p.page}</p>
                {p.warnings.map((w, i) => (
                  <p key={i} className="notice">
                    {w}
                  </p>
                ))}
                <CourseText text={p.text} />
              </section>
            ))}
          </div>
        )}
      </div>
      <footer className="setup-preview__foot">
        {doc.status === 'processing' && (
          <p className="muted">
            Lodestar is reading this file. You can look at the original while you wait.
          </p>
        )}
        {doc.status === 'failed' && <p role="alert">{doc.error}</p>}
        {doc.status === 'review' && (
          <>
            {flagged.length > 0 && (
              <p className="notice">
                {flagged.length} page{flagged.length > 1 ? 's' : ''} flagged: compare them with the
                original{unclear ? ' and replace every [unclear] before validating' : ''}.
              </p>
            )}
            {error && <p role="alert">{error}</p>}
            <div className="setup-preview__actions">
              {flagged.length > 0 && (
                <button type="button" onClick={onReview}>
                  Review and edit pages
                </button>
              )}
              <button
                type="button"
                className="primary"
                data-testid="setup-validate"
                disabled={busy || unclear}
                onClick={() => {
                  setBusy(true)
                  setError('')
                  api.approveDocument(doc.doc_id).then(onApproved, (e: unknown) => {
                    setError(e instanceof Error ? e.message : 'Could not validate this document.')
                    setBusy(false)
                  })
                }}
              >
                It matches the original: validate
              </button>
            </div>
          </>
        )}
        {doc.status === 'ready' && (
          <p className="muted">Validated. Lodestar can explain and quiz you from it.</p>
        )}
      </footer>
    </aside>
  )
}

export function SubjectSetup({ onDone }: { onDone: () => void }) {
  const [subject, setSubject] = useState<SubjectView | null>(null)
  const [name, setName] = useState('')
  const [docs, setDocs] = useState<DocumentView[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [reviewing, setReviewing] = useState(false)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(0)
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const refresh = useCallback(() => {
    if (!subject) return
    api.documents().then(
      (all) => {
        setDocs(all.filter((d) => d.subject_id === subject.subject_id))
      },
      () => undefined,
    )
  }, [subject])

  // Poll while anything is still being read.
  const reading = docs.some((d) => d.status === 'processing') || uploading > 0
  useEffect(() => {
    if (!reading) return
    const timer = window.setInterval(refresh, 1500)
    return () => {
      window.clearInterval(timer)
    }
  }, [reading, refresh])

  const upload = (files: FileList | File[] | null) => {
    if (!files || !subject) return
    const list = Array.from(files).filter((f) => /\.(pdf|txt|md)$/i.test(f.name))
    if (!list.length) {
      setError('Lodestar reads PDF, .txt and .md files.')
      return
    }
    setError('')
    for (const file of list) {
      setUploading((n) => n + 1)
      api
        .uploadDocument(file, subject.subject_id, '')
        .then(
          (doc) => {
            setDocs((d) => [doc, ...d.filter((x) => x.doc_id !== doc.doc_id)])
            setSelected((s) => s ?? doc.doc_id)
          },
          (e: unknown) => {
            setError(`${file.name}: ${e instanceof Error ? e.message : 'upload failed'}`)
          },
        )
        .finally(() => {
          setUploading((n) => n - 1)
        })
    }
  }

  const current = docs.find((d) => d.doc_id === selected) ?? null
  const validated = docs.filter((d) => d.status === 'ready').length

  if (!subject) {
    return (
      <main className="solo">
        <section className="card setup-start" data-testid="subject-setup">
          <p className="eyebrow">Step 1 of 2</p>
          <h2>What are you studying?</h2>
          <p>
            Name a subject, then import its course files: lecture notes, slides, handouts. Lodestar
            explains and quizzes you from your own course, and cites the page every time.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!name.trim()) return
              api.createSubject(name.trim()).then(setSubject, (err: unknown) => {
                setError(err instanceof Error ? err.message : 'Could not create the subject.')
              })
            }}
          >
            <input
              value={name}
              maxLength={100}
              placeholder="e.g. Probability, Object-oriented C++, Thermodynamics"
              aria-label="Subject name"
              data-testid="subject-name"
              onChange={(e) => {
                setName(e.target.value)
              }}
            />
            <button type="submit" className="primary" disabled={!name.trim()}>
              Continue
            </button>
          </form>
          {error && <p role="alert">{error}</p>}
          <button type="button" className="link" onClick={onDone}>
            Skip for now and look around with the sample course
          </button>
        </section>
      </main>
    )
  }

  return (
    <main className="setup" data-testid="subject-import">
      <section className="setup-list">
        <p className="eyebrow">Step 2 of 2 · {subject.name}</p>
        <h2>Import your course files</h2>
        <p className="muted">
          Drop the PDFs of this subject. Open each one to check it next to the original, then
          validate it. Lodestar only uses what you validated.
        </p>
        <button
          type="button"
          className={dragging ? 'setup-drop setup-drop--over' : 'setup-drop'}
          onClick={() => input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => {
            setDragging(false)
          }}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            upload(e.dataTransfer.files)
          }}
        >
          <strong>Drop PDFs here</strong>
          <span className="muted small">
            or click to choose files · PDF, .txt, .md · up to 25 MB
          </span>
        </button>
        <input
          ref={input}
          type="file"
          multiple
          accept=".pdf,.txt,.md"
          hidden
          data-testid="setup-files"
          onChange={(e) => {
            upload(e.target.files)
            e.target.value = ''
          }}
        />
        {error && <p role="alert">{error}</p>}
        {uploading > 0 && <p className="muted small">Uploading {uploading}…</p>}
        <ul className="setup-files">
          {docs.map((d) => (
            <li key={d.doc_id}>
              <button
                type="button"
                aria-pressed={d.doc_id === selected}
                className={`setup-file setup-file--${d.status}`}
                onClick={() => {
                  setSelected(d.doc_id)
                  setReviewing(false)
                }}
              >
                <span className="setup-file__name">{d.title}</span>
                <span className="setup-file__status">{statusText(d)}</span>
                {d.status === 'processing' && d.pages > 0 && (
                  <span className="setup-file__bar" aria-hidden="true">
                    <span style={{ width: `${String((100 * d.progress) / d.pages)}%` }} />
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
        <div className="setup-done">
          <p className="muted small">
            {validated} of {docs.length} validated
          </p>
          <button
            type="button"
            className="primary"
            disabled={validated === 0}
            data-testid="setup-finish"
            onClick={onDone}
          >
            Start studying
          </button>
        </div>
      </section>
      {current && reviewing ? (
        <div className="setup-preview">
          <DocumentReview
            doc={current}
            onSaved={(doc) => {
              setDocs((all) => all.map((d) => (d.doc_id === doc.doc_id ? doc : d)))
              setReviewing(false)
            }}
            onClose={() => {
              setReviewing(false)
            }}
          />
        </div>
      ) : current ? (
        <Preview
          key={current.doc_id}
          doc={current}
          onApproved={(doc) => {
            setDocs((all) => all.map((d) => (d.doc_id === doc.doc_id ? doc : d)))
          }}
          onReview={() => {
            setReviewing(true)
          }}
        />
      ) : (
        <aside className="setup-preview setup-preview--empty">
          <p className="muted">Your document will show here, page by page.</p>
        </aside>
      )}
    </main>
  )
}
