import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { DocumentView } from '../api/types'
import { CourseText } from '../lib/math'
import { t, useLocale } from '../i18n'

export function DocumentReview({
  doc,
  onSaved,
  onClose,
}: {
  doc: DocumentView
  onSaved: (doc: DocumentView) => void
  onClose: () => void
}) {
  useLocale()
  const panel = useRef<HTMLElement>(null)
  const [pages, setPages] = useState<{ page: number; text: string; warnings: string[] }[]>([])
  const [page, setPage] = useState(0)
  const [pdf, setPdf] = useState('')
  const [checked, setChecked] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    panel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    let active = true
    let url = ''
    api.documentPages(doc.doc_id).then(
      (p) => {
        if (active) setPages(p)
      },
      () => {
        if (active) setError(t('Could not load extracted pages.'))
      },
    )
    if (doc.filename.toLowerCase().endsWith('.pdf'))
      api.documentOriginal(doc.doc_id).then(
        (blob) => {
          if (active) {
            url = URL.createObjectURL(blob)
            setPdf(url)
          }
        },
        () => {
          if (active)
            setError(t('The original PDF is unavailable. Compare against your local copy.'))
        },
      )
    return () => {
      active = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [doc.doc_id, doc.filename])
  const current = pages[page]
  const unresolved = pages.some((p) => p.text.includes('[unclear]'))
  return (
    <section ref={panel} className="card document-review" aria-label={t('Review extracted pages')}>
      <div className="documents__actions">
        <h2>{t('Check the course against the original')}</h2>
        <button onClick={onClose}>{t('Close review')}</button>
      </div>
      <p className="muted">
        {t(
          'Compare the original with the extracted text. Correct any mistakes, then validate your chapter to start studying. You can edit the text directly; formulas update in the preview.',
        )}
      </p>
      <label>
        {t('Page')}
        <select
          value={page}
          onChange={(e) => {
            setPage(Number(e.target.value))
          }}
        >
          {pages.map((p, i) => (
            <option key={p.page} value={i}>
              {t('Page {page}', { page: p.page })}
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
                {t('Open original PDF')}
              </a>
              <iframe title={t('Original course PDF')} src={`${pdf}#page=${String(page + 1)}`} />
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
                {t('Extracted page text')}
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
              <p className="eyebrow">{t('Formula preview')}</p>
              <CourseText text={current.text} />
            </>
          )}
        </div>
      </div>
      {unresolved && (
        <p className="notice">
          {t('Replace all [unclear] markers by checking the original before approving.')}
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
        {t('I checked every page and formula against the original.')}
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
            .then(onSaved, (e: unknown) => {
              setError(
                e instanceof Error
                  ? e.message
                  : t('Could not save the reviewed pages. Please try again.'),
              )
              setBusy(false)
            })
        }}
      >
        {t('Validate chapter')}
      </button>
    </section>
  )
}
