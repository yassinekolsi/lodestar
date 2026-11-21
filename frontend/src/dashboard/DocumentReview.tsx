import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { DocumentView } from '../api/types'
import { CourseText } from '../lib/math'
import { t, useLocale } from '../i18n'

const LANGUAGE_LABELS: Record<'original' | 'en' | 'fr' | 'tn', () => string> = {
  original: () => t('Original'),
  en: () => 'English',
  fr: () => 'Français',
  tn: () => 'تونسي',
}

export function DocumentReview({
  doc,
  onSaved,
  onClose,
}: {
  doc: DocumentView
  onSaved: (doc: DocumentView) => void
  onClose: () => void
}) {
  const locale = useLocale()
  const panel = useRef<HTMLElement>(null)
  const [pages, setPages] = useState<
    { page: number; text: string; warnings: string[]; translations?: Record<string, string> }[]
  >([])
  const [reading, setReading] = useState<string>('original')
  const [pdf, setPdf] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    panel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    let active = true
    let url = ''
    api.documentPages(doc.doc_id).then(
      (p) => {
        if (active) {
          setPages(p)
          setLoading(false)
        }
      },
      () => {
        if (active) {
          setError(t('Could not load extracted pages.'))
          setLoading(false)
        }
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

  const save = async () => {
    if (busy || loading || !pages.length) return
    setBusy(true)
    setError('')
    try {
      const saved = await api.reviewDocument(
        doc.doc_id,
        pages.map((p) => p.text),
      )
      onSaved(saved)
    } catch (e) {
      setError(
        e instanceof Error ? e.message : t('Could not save the reviewed pages. Please try again.'),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section ref={panel} className="card document-review" aria-label={t('Review extracted pages')}>
      <div className="documents__actions">
        <h2>{doc.title}</h2>
        <button disabled={busy} onClick={onClose}>
          {t('Close review')}
        </button>
      </div>
      <p className="muted">
        {t(
          'Read the full chapter below. Compare it with the original, correct anything that needs attention, then validate to start studying.',
        )}
      </p>
      {loading && <p role="status">{t('Loading your chapter…')}</p>}
      {pages.some((p) => p.translations && Object.keys(p.translations).length) && (
        <div className="document-review__languages" role="group" aria-label={t('Read in')}>
          {(['original', 'en', 'fr', 'tn'] as const).map((lang) => (
            <button
              key={lang}
              aria-pressed={reading === lang}
              className={reading === lang ? 'primary' : ''}
              onClick={() => {
                setReading(lang)
              }}
            >
              {LANGUAGE_LABELS[lang]()}
            </button>
          ))}
          {reading === 'original' && locale !== 'en' && (
            <span className="muted small">{t('Translations come from the same reading.')}</span>
          )}
        </div>
      )}
      <div className={`document-review__pages${pdf ? '' : ' document-review__pages--text'}`}>
        {pdf && (
          <div className="document-review__original">
            <a href={pdf} target="_blank" rel="noreferrer">
              {t('Open original PDF')}
            </a>
            <iframe title={t('Original course PDF')} src={`${pdf}#view=FitH&navpanes=0`} />
          </div>
        )}
        <div className="document-review__chapter">
          {pages.map((p, index) => (
            <article key={p.page} className="document-review__section">
              {p.warnings.map((warning, i) => (
                <p key={i} className="notice">
                  {warning}
                </p>
              ))}
              <div
                className="document-review__text"
                dir={reading === 'tn' && p.translations?.tn ? 'rtl' : undefined}
              >
                <CourseText
                  text={(reading !== 'original' && p.translations?.[reading]) || p.text}
                />
              </div>
              <details open={p.text.includes('[unclear]') || undefined}>
                <summary>{t('Edit extracted text')}</summary>
                <label className="sr-only" htmlFor={`review-text-${String(p.page)}`}>
                  {t('Extracted page text')}
                </label>
                <textarea
                  id={`review-text-${String(p.page)}`}
                  value={p.text}
                  disabled={busy}
                  onChange={(e) => {
                    const text = e.target.value
                    setPages((previous) =>
                      previous.map((item, i) => (i === index ? { ...item, text } : item)),
                    )
                  }}
                />
              </details>
            </article>
          ))}
        </div>
      </div>
      <footer className="document-review__footer">
        {error && (
          <p role="alert" className="notice">
            {error}
          </p>
        )}
        <p className="muted small">
          {t(
            'Validating saves your reviewed chapter. Search indexing continues in the background.',
          )}
        </p>
        <button
          className="primary"
          disabled={busy || loading || !pages.length}
          onClick={() => {
            void save()
          }}
        >
          {busy ? t('Saving chapter…') : t('Validate chapter')}
        </button>
      </footer>
    </section>
  )
}
