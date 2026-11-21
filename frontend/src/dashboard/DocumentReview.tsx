import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { DocumentView } from '../api/types'
import { CourseText } from '../lib/math'

export function DocumentReview({
  doc,
  onSaved,
  onClose,
}: {
  doc: DocumentView
  onSaved: (doc: DocumentView) => void
  onClose: () => void
}) {
  const [pages, setPages] = useState<{ page: number; text: string; warnings: string[] }[]>([])
  const [page, setPage] = useState(0)
  const [pdf, setPdf] = useState('')
  const [checked, setChecked] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    let url = ''
    api.documentPages(doc.doc_id).then(
      (p) => {
        if (active) setPages(p)
      },
      () => {
        if (active) setError('Could not load extracted pages.')
      },
    )
    api.documentOriginal(doc.doc_id).then(
      (blob) => {
        if (active) {
          url = URL.createObjectURL(blob)
          setPdf(url)
        }
      },
      () => {
        if (active) setError('The original PDF is unavailable. Compare against your local copy.')
      },
    )
    return () => {
      active = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [doc.doc_id])
  const current = pages[page]
  const unresolved = pages.some((p) => p.text.includes('[unclear]'))
  return (
    <section className="card document-review" aria-label="Review extracted pages">
      <div className="documents__actions">
        <h2>Check the course against the original</h2>
        <button onClick={onClose}>Close review</button>
      </div>
      <p className="muted">
        OCR can confuse a minus sign, exponent or probability bar. Check every page and edit any
        mistakes before using this chapter for explanations or quizzes. The preview shows how
        formulas will look to you.
      </p>
      <label>
        Page
        <select
          value={page}
          onChange={(e) => {
            setPage(Number(e.target.value))
          }}
        >
          {pages.map((p, i) => (
            <option key={p.page} value={i}>
              Page {p.page}
              {p.warnings.length ? ' · flagged' : ''}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
      <div className="document-review__pages">
        <div>
          {pdf && (
            <>
              <a href={pdf} target="_blank" rel="noreferrer">
                Open original PDF
              </a>
              <iframe title="Original course PDF" src={`${pdf}#page=${String(page + 1)}`} />
            </>
          )}
        </div>
        <div>
          {current && (
            <>
              {current.warnings.map((w, i) => (
                <p key={i} className="notice">
                  {w}
                </p>
              ))}
              <label>
                Extracted page text
                <textarea
                  value={current.text}
                  onChange={(e) => {
                    const text = e.target.value
                    setChecked(false)
                    setPages((previous) =>
                      previous.map((p, i) => (i === page ? { ...p, text } : p)),
                    )
                  }}
                />
              </label>
              <p className="eyebrow">Formula preview</p>
              <CourseText text={current.text} />
            </>
          )}
        </div>
      </div>
      {unresolved && (
        <p className="notice">
          Replace all [unclear] markers by checking the original before approving.
        </p>
      )}
      <label>
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => {
            setChecked(e.target.checked)
          }}
        />
        I checked every page and formula against the original.
      </label>
      <button
        className="primary"
        disabled={busy || !checked || unresolved || !pages.length}
        onClick={() => {
          setBusy(true)
          setError('')
          api
            .reviewDocument(
              doc.doc_id,
              pages.map((p) => p.text),
            )
            .then(onSaved, () => {
              setError('Could not save the reviewed pages. Please try again.')
              setBusy(false)
            })
        }}
      >
        Save reviewed chapter
      </button>
    </section>
  )
}
