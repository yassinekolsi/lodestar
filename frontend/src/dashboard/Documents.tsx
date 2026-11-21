import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type { DocumentView, PassageView, SubjectView } from '../api/types'
import { CourseText } from '../lib/math'
import { DocumentReview } from './DocumentReview'

export function Documents({ onAsk }: { onAsk: (message: string) => void }) {
  const [subjects, setSubjects] = useState<SubjectView[]>([])
  const [docs, setDocs] = useState<DocumentView[]>([])
  const [subject, setSubject] = useState('')
  const [name, setName] = useState('')
  const [chapter, setChapter] = useState('')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState('')
  const [hits, setHits] = useState<PassageView[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [gemini, setGemini] = useState(false)
  const [reviewing, setReviewing] = useState<DocumentView | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let active = true
    Promise.all([api.subjects(), api.documents()]).then(
      ([s, d]) => {
        if (active) {
          setSubjects(s)
          setDocs(d)
        }
      },
      () => {
        if (active) setError('Could not load your library. Try reopening this page.')
      },
    )
    return () => {
      active = false
    }
  }, [])

  const run = async (work: () => Promise<void>) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await work()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const upload = (files: FileList | null) => {
    if (!files?.length || busy) return
    void run(async () => {
      for (const file of Array.from(files)) {
        if (file.size > 25 * 1024 * 1024) throw new Error(`${file.name} is over 25 MB.`)
        setNotice(`Reading ${file.name}. Scanned pages may take a few minutes.`)
        const doc = await api.uploadDocument(file, subject, chapter, gemini)
        setDocs((previous) => [doc, ...previous])
        setNotice(
          doc.review_required
            ? 'Gemini has read your chapter. Review its pages and formulas before studying from it.'
            : doc.searchable
              ? 'Your chapter is ready. Search its pages or check your understanding.'
              : 'Your chapter is saved. Search is temporarily unavailable; you can still try a quiz.',
        )
      }
      if (fileInput.current) fileInput.current.value = ''
    })
  }

  const visible = docs.filter((d) => !subject || d.subject_id === subject)
  return (
    <div className="documents">
      <section className="card">
        <p className="eyebrow">Your study library</p>
        <h2>Bring the course you are actually studying</h2>
        <p className="muted">
          Organise your chapters by subject. Lodestar uses your passages to explain ideas and cite
          the page, so you can check the answer against your course.
        </p>
        <form
          className="inline-ask"
          onSubmit={(e) => {
            e.preventDefault()
            void run(async () => {
              const created = await api.createSubject(name.trim())
              setSubjects((previous) => [...previous, created])
              setSubject(created.subject_id)
              setName('')
            })
          }}
        >
          <input
            aria-label="New subject"
            placeholder="e.g. C++ or Probability"
            value={name}
            maxLength={100}
            onChange={(e) => {
              setName(e.target.value)
            }}
          />
          <button disabled={busy || !name.trim()}>Add subject</button>
        </form>
        <div className="documents__fields">
          <label>
            Subject
            <select
              aria-label="Subject"
              value={subject}
              disabled={busy}
              onChange={(e) => {
                setSubject(e.target.value)
                setSelected('')
                setHits(null)
              }}
            >
              <option value="">All subjects / unfiled upload</option>
              {subjects.map((s) => (
                <option key={s.subject_id} value={s.subject_id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Chapter label
            <input
              placeholder="e.g. Operator overloading"
              maxLength={120}
              value={chapter}
              disabled={busy}
              onChange={(e) => {
                setChapter(e.target.value)
              }}
            />
          </label>
        </div>
        <div
          className="documents__drop"
          onDragOver={(e) => {
            e.preventDefault()
          }}
          onDrop={(e) => {
            e.preventDefault()
            upload(e.dataTransfer.files)
          }}
        >
          <strong>Drop your chapters here</strong>
          <p className="muted small">
            PDF, Markdown or text · up to 25 MB each. Scans use Gemini OCR with Cloud AI enabled.
          </p>
          <label>
            <input
              type="checkbox"
              checked={gemini}
              disabled={busy}
              onChange={(e) => {
                setGemini(e.target.checked)
              }}
            />
            Use Gemini for every PDF page, including formulas and diagrams
          </label>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept=".pdf,.txt,.md"
            aria-label="Upload course files"
            disabled={busy}
            onChange={(e) => {
              upload(e.target.files)
            }}
          />
        </div>
      </section>
      {error && (
        <p role="alert" className="notice">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {reviewing && (
        <DocumentReview
          doc={reviewing}
          onClose={() => {
            setReviewing(null)
          }}
          onSaved={(doc) => {
            setDocs((previous) => previous.map((d) => (d.doc_id === doc.doc_id ? doc : d)))
            setReviewing(null)
          }}
        />
      )}
      <section className="panel-block" aria-label="Your chapters">
        <h2>Your chapters</h2>
        {!visible.length && <p className="muted">Add a subject and upload a chapter to begin.</p>}
        <div className="documents__grid">
          {visible.map((doc) => (
            <article key={doc.doc_id} className="card">
              <p className="eyebrow">
                {subjects.find((s) => s.subject_id === doc.subject_id)?.name ?? 'Unfiled'}
                {doc.chapter ? ` · ${doc.chapter}` : ''}
              </p>
              <h3>{doc.title}</h3>
              <p className="muted small">
                {doc.filename} · {doc.pages} pages · {doc.passages} passages
              </p>
              <p className="muted small">
                {Object.keys(doc.concepts).length
                  ? 'Linked to concepts in your study map.'
                  : 'Practice from this chapter does not change course mastery unless its concepts match the study map.'}
              </p>
              <div className="documents__actions">
                <button
                  disabled={busy}
                  onClick={() => {
                    setReviewing(doc)
                  }}
                >
                  Review pages and formulas
                </button>
                {doc.review_required && (
                  <p className="notice">
                    Review required · excluded from study answers and quizzes
                  </p>
                )}
                <button
                  disabled={busy}
                  onClick={() => {
                    setSelected(doc.doc_id)
                    setHits(null)
                  }}
                >
                  Search this chapter
                </button>
                <button
                  disabled={busy || doc.review_required}
                  onClick={() => {
                    onAsk(`Quiz me on my notes [document:${doc.doc_id}]`)
                  }}
                  aria-disabled={doc.review_required}
                >
                  Check understanding
                </button>
                <button
                  disabled={busy}
                  aria-label={`Remove ${doc.title}`}
                  onClick={() =>
                    void run(async () => {
                      await api.deleteDocument(doc.doc_id)
                      setDocs((previous) => previous.filter((d) => d.doc_id !== doc.doc_id))
                      setHits(null)
                      if (selected === doc.doc_id) setSelected('')
                    })
                  }
                >
                  Remove
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="card" aria-label="Search course passages">
        <h2>Find the passage behind an idea</h2>
        <label>
          Search in
          <select
            aria-label="Search in"
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value)
              setHits(null)
            }}
          >
            <option value="">All my documents</option>
            {docs.map((d) => (
              <option key={d.doc_id} value={d.doc_id}>
                {d.title}
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
            aria-label="Search your notes"
            placeholder="Use terms from your notes, such as vector or conditional probability"
            value={query}
            maxLength={500}
            onChange={(e) => {
              setQuery(e.target.value)
            }}
          />
          <button disabled={busy || !query.trim()}>Search passages</button>
        </form>
        {hits?.length === 0 && <p>No matching passage. Try a term used in your chapter.</p>}
        {hits?.map((hit, i) => (
          <article
            className="documents__passage"
            key={`${hit.doc_id}-${String(hit.page)}-${String(i)}`}
          >
            <strong>
              {hit.title} · page {hit.page}
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
              Help me understand this
            </button>
          </article>
        ))}
      </section>
    </div>
  )
}
