import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { DocumentView, PassageView, SubjectView } from '../api/types'
import { t, useLocale } from '../i18n'
import { CourseText } from '../lib/math'
import { DocumentReview } from './DocumentReview'

export function Documents({ onAsk }: { onAsk: (message: string) => void }) {
  useLocale()
  const [subjects, setSubjects] = useState<SubjectView[]>([])
  const [docs, setDocs] = useState<DocumentView[]>([])
  const [subject, setSubject] = useState('')
  const [filter, setFilter] = useState('')
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [chapter, setChapter] = useState('')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState('')
  const [hits, setHits] = useState<PassageView[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [gemini, setGemini] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [reviewing, setReviewing] = useState<DocumentView | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [offline, setOffline] = useState(false)
  const [indexChecks, setIndexChecks] = useState(0)
  const [uploading, setUploading] = useState('')
  const [failed, setFailed] = useState<{ file: File; error: string }[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const searchPanel = useRef<HTMLDetailsElement>(null)
  const processing = docs.some((doc) => doc.status === 'processing')
  const polling =
    processing ||
    (indexChecks < 120 && docs.some((doc) => doc.status === 'ready' && !doc.searchable))

  useEffect(() => {
    let active = true
    Promise.all([api.subjects(), api.documents()]).then(
      ([s, d]) => {
        if (active) {
          setSubjects((previous) => [
            ...previous,
            ...s.filter((item) => !previous.some((p) => p.subject_id === item.subject_id)),
          ])
          setDocs((previous) => [
            ...previous,
            ...d.filter((item) => !previous.some((p) => p.doc_id === item.doc_id)),
          ])
          setLoading(false)
        }
      },
      () => {
        if (active) {
          setOffline(true)
          setLoading(false)
        }
      },
    )
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!polling || busy) return
    let active = true
    let timer: number | undefined
    const poll = async () => {
      try {
        const next = await api.documents()
        if (active) {
          setDocs(next)
          setOffline(false)
        }
      } catch {
        if (active) setOffline(true)
      } finally {
        if (active) setIndexChecks((previous) => previous + 1)
        if (active)
          timer = window.setTimeout(() => {
            void poll()
          }, 2500)
      }
    }
    timer = window.setTimeout(() => {
      void poll()
    }, 1500)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [polling, busy])

  const run = async (work: () => Promise<void>) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await work()
    } catch (e) {
      setError(e instanceof Error ? e.message : t('Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  const upload = (files: FileList | File[] | null) => {
    if (!files?.length || busy) return
    void run(async () => {
      for (const file of Array.from(files)) {
        setFailed((previous) => previous.filter((item) => item.file !== file))
        setUploading(file.name)
        try {
          if (file.size > 25 * 1024 * 1024) throw new Error(t('This file is over 25 MB.'))
          if (!/\.(pdf|txt|md)$/i.test(file.name))
            throw new Error(t('Choose a PDF, Markdown or text file.'))
          const doc = await api.uploadDocument(file, subject, chapter, gemini)
          setDocs((previous) => [doc, ...previous.filter((d) => d.doc_id !== doc.doc_id)])
          setFilter('')
          setNotice(t('File received. We are reading its pages.'))
        } catch (e) {
          setFailed((previous) => [
            ...previous,
            { file, error: e instanceof Error ? e.message : t('Please try again.') },
          ])
        }
      }
      setUploading('')
      if (fileInput.current) fileInput.current.value = ''
    })
  }

  const visible = docs.filter((d) => !filter || d.subject_id === filter)
  const canStudy = (doc: DocumentView) => doc.status === 'ready' && !doc.review_required
  const searchThis = (doc: DocumentView) => {
    setSelected(doc.doc_id)
    setHits(null)
    if (searchPanel.current) {
      searchPanel.current.open = true
      searchPanel.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  return (
    <div className="documents">
      <header className="documents__heading">
        <div>
          <p className="eyebrow">{t('Your study library')}</p>
          <h2>{t('Your course. Your pace.')}</h2>
          <p className="muted">
            {t('Add a chapter, check its pages, then study from your own notes.')}
          </p>
        </div>
        <span className="documents__steps">{t('Upload → Review → Study')}</span>
      </header>
      <section className="card documents__import" aria-label={t('Add course files')}>
        <div className="documents__destination">
          <label>
            {t('Subject')}
            <select
              aria-label={t('Subject')}
              value={subject}
              disabled={busy}
              onChange={(e) => {
                setSubject(e.target.value)
              }}
            >
              <option value="">{t('Choose a subject (optional)')}</option>
              {subjects.map((s) => (
                <option key={s.subject_id} value={s.subject_id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setCreating(!creating)
            }}
          >
            {t('New subject')}
          </button>
        </div>
        {creating && (
          <form
            className="inline-ask"
            onSubmit={(e) => {
              e.preventDefault()
              void run(async () => {
                const created = await api.createSubject(name.trim())
                setSubjects((previous) => [...previous, created])
                setSubject(created.subject_id)
                setName('')
                setCreating(false)
              })
            }}
          >
            <input
              aria-label={t('New subject')}
              placeholder={t('e.g. C++ or Probability')}
              value={name}
              maxLength={100}
              autoFocus
              onChange={(e) => {
                setName(e.target.value)
              }}
            />
            <button disabled={busy || !name.trim()}>{t('Add subject')}</button>
          </form>
        )}
        <div
          className={`documents__drop${dragging ? ' documents__drop--active' : ''}`}
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
          <span className="documents__upload-mark" aria-hidden="true">
            ↑
          </span>
          <h3>
            {uploading ? t('Uploading {name}', { name: uploading }) : t('Drop your chapters here')}
          </h3>
          <p className="muted">{t('PDF, Markdown or text · up to 25 MB per file')}</p>
          <button
            className="primary"
            disabled={busy}
            onClick={() => {
              fileInput.current?.click()
            }}
          >
            {t('Choose files')}
          </button>
          <input
            ref={fileInput}
            className="documents__file-input"
            type="file"
            tabIndex={-1}
            multiple
            accept=".pdf,.txt,.md"
            aria-label={t('Upload course files')}
            disabled={busy}
            onChange={(e) => {
              upload(e.target.files)
            }}
          />
          <p className="small muted">
            {t('Scanned pages use Gemini. You review the result before studying.')}
          </p>
        </div>
        <details className="documents__options">
          <summary>{t('Import options')}</summary>
          <label>
            {t('Chapter label')}
            <input
              aria-label={t('Chapter label')}
              value={chapter}
              maxLength={120}
              placeholder={t('Optional chapter name')}
              onChange={(e) => {
                setChapter(e.target.value)
              }}
            />
          </label>
          <label className="documents__checkbox">
            <input
              type="checkbox"
              checked={gemini}
              disabled={busy}
              onChange={(e) => {
                setGemini(e.target.checked)
              }}
            />
            {t('Use Gemini for every PDF page, including formulas and diagrams')}
          </label>
        </details>
      </section>
      {offline && (
        <div role="status" className="notice documents__connection">
          <span>
            {t('Connection interrupted. Your library will refresh when the server returns.')}
          </span>
          <button
            disabled={busy}
            onClick={() => {
              void run(async () => {
                const [s, d] = await Promise.all([api.subjects(), api.documents()])
                setSubjects(s)
                setDocs(d)
                setOffline(false)
              })
            }}
          >
            {t('Refresh library')}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="notice">
          {error}
        </p>
      )}
      {notice && processing && (
        <p role="status" className="documents__notice">
          {notice}
        </p>
      )}
      {failed.map((item, i) => (
        <div
          role="alert"
          className="notice documents__connection"
          key={`${item.file.name}-${String(i)}`}
        >
          <span>
            <strong>{item.file.name}</strong>
            <br />
            {item.error}
          </span>
          <button
            disabled={busy}
            onClick={() => {
              upload([item.file])
            }}
          >
            {t('Try again')}
          </button>
          <button
            disabled={busy}
            onClick={() => {
              setFailed((previous) => previous.filter((f) => f !== item))
            }}
          >
            {t('Dismiss')}
          </button>
        </div>
      ))}
      {reviewing && (
        <DocumentReview
          doc={reviewing}
          onClose={() => {
            setReviewing(null)
          }}
          onSaved={(doc) => {
            setIndexChecks(0)
            setDocs((previous) => previous.map((d) => (d.doc_id === doc.doc_id ? doc : d)))
            setReviewing(null)
          }}
        />
      )}
      <section className="panel-block" aria-label={t('Your chapters')}>
        <h2>{t('Your chapters')}</h2>
        {subjects.length > 0 && (
          <nav className="documents__filters" aria-label={t('Filter subjects')}>
            <button
              aria-pressed={!filter}
              onClick={() => {
                setFilter('')
              }}
            >
              {t('All subjects')}
            </button>
            {subjects.map((s) => (
              <button
                key={s.subject_id}
                aria-pressed={filter === s.subject_id}
                onClick={() => {
                  setFilter(s.subject_id)
                }}
              >
                {s.name}
              </button>
            ))}
          </nav>
        )}
        {loading ? (
          <p role="status">{t('Loading your library…')}</p>
        ) : (
          !visible.length && (
            <div className="documents__empty">
              <h3>{t('Your next study session starts here')}</h3>
              <p className="muted">{t('Add a subject and upload a chapter to begin.')}</p>
            </div>
          )
        )}
        <div className="documents__grid">
          {visible.map((doc) => (
            <article key={doc.doc_id} className="card documents__chapter">
              <div className="documents__chapter-top">
                <p className="eyebrow">
                  {subjects.find((s) => s.subject_id === doc.subject_id)?.name ?? t('Unfiled')}
                </p>
                <span className={`documents__status documents__status--${doc.status}`}>
                  {doc.status === 'processing'
                    ? t('Reading')
                    : doc.status === 'failed'
                      ? t('Needs attention')
                      : canStudy(doc)
                        ? t('Ready to study')
                        : t('Ready for review')}
                </span>
              </div>
              <h3>{doc.title}</h3>
              {doc.chapter && doc.chapter !== doc.title && (
                <p className="small muted">{doc.chapter}</p>
              )}
              <p className="small muted documents__filename">
                {doc.filename} · {t('{count} pages', { count: doc.pages })}
              </p>
              {doc.status === 'processing' ? (
                <div className="documents__processing" role="status">
                  <progress
                    value={Math.min(doc.progress, doc.pages)}
                    max={Math.max(doc.pages, 1)}
                    aria-label={t('Reading {name}', { name: doc.title })}
                  />
                  <p>
                    {doc.progress
                      ? t('Checking page {current} of {total}', {
                          current: doc.progress,
                          total: doc.pages,
                        })
                      : t('Preparing your chapter…')}
                  </p>
                  <p className="small muted">
                    {t('Your file is saved. Reading continues in the background.')}
                  </p>
                </div>
              ) : doc.status === 'failed' ? (
                <p role="alert" className="notice">
                  {doc.error || t('We could not read this file. Please upload it again.')}
                </p>
              ) : (
                <>
                  {!canStudy(doc) && (
                    <p className="small muted">
                      {t(
                        'Check the text and formulas against the original, then validate your chapter.',
                      )}
                    </p>
                  )}
                  <div className="documents__actions">
                    {canStudy(doc) && (
                      <button
                        className="primary"
                        onClick={() => {
                          onAsk(`Quiz me on my notes [document:${doc.doc_id}]`)
                        }}
                      >
                        {t('Check understanding')}
                      </button>
                    )}
                    <button
                      className={canStudy(doc) ? '' : 'primary'}
                      onClick={() => {
                        setReviewing(doc)
                      }}
                    >
                      {t('Review pages and formulas')}
                    </button>
                    {canStudy(doc) && (
                      <button
                        onClick={() => {
                          searchThis(doc)
                        }}
                      >
                        {t('Search this chapter')}
                      </button>
                    )}
                  </div>
                </>
              )}
              <footer className="documents__chapter-footer">
                <span className="small muted">
                  {canStudy(doc)
                    ? doc.searchable
                      ? t('Answers cite your pages.')
                      : t('You can study now. Search is not ready yet.')
                    : t('Available for study after validation.')}
                </span>
                <button
                  className="documents__remove"
                  disabled={busy}
                  aria-label={t('Remove {name}', { name: doc.title })}
                  onClick={() => {
                    void run(async () => {
                      await api.deleteDocument(doc.doc_id)
                      setDocs((previous) => previous.filter((d) => d.doc_id !== doc.doc_id))
                      if (selected === doc.doc_id) {
                        setSelected('')
                        setHits(null)
                      }
                    })
                  }}
                >
                  {t('Remove')}
                </button>
              </footer>
            </article>
          ))}
        </div>
      </section>
      <details className="card documents__search" ref={searchPanel}>
        <summary>{t('Find the passage behind an idea')}</summary>
        <label>
          {t('Search in')}
          <select
            aria-label={t('Search in')}
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value)
              setHits(null)
            }}
          >
            <option value="">{t('All my documents')}</option>
            {docs.filter(canStudy).map((doc) => (
              <option key={doc.doc_id} value={doc.doc_id}>
                {doc.title}
              </option>
            ))}
          </select>
        </label>
        <form
          className="inline-ask"
          onSubmit={(e) => {
            e.preventDefault()
            void run(async () => {
              setHits(await api.searchDocuments(query.trim(), selected))
            })
          }}
        >
          <input
            aria-label={t('Search your notes')}
            placeholder={t('Use a term from your chapter')}
            value={query}
            maxLength={500}
            onChange={(e) => {
              setQuery(e.target.value)
            }}
          />
          <button disabled={busy || !query.trim()}>{t('Search passages')}</button>
        </form>
        {hits?.length === 0 && <p>{t('No matching passage. Try a term used in your chapter.')}</p>}
        {hits?.map((hit, i) => (
          <article
            className="documents__passage"
            key={`${hit.doc_id}-${String(hit.page)}-${String(i)}`}
          >
            <strong>
              {hit.title} · {t('page {page}', { page: hit.page })}
            </strong>
            <div>
              <CourseText text={hit.text} />
            </div>
            <button
              disabled={busy}
              onClick={() => {
                onAsk(`Explain this idea from my notes: ${query} [document:${hit.doc_id}]`)
              }}
            >
              {t('Help me understand this')}
            </button>
          </article>
        ))}
      </details>
    </div>
  )
}
