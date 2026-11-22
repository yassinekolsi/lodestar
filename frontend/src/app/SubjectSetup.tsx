import { useEffect, useRef, useState } from 'react'

import { api, startDemo } from '../api/client'
import type { SubjectView } from '../api/types'
import { t, useLocale } from '../i18n'

/** First visit: import your own documents, or explore as a guest (the demo person). Studying needs
 * a document of one's own, so there is no third way in. "Import documents" opens the file picker
 * straight away; the subject is chosen after the files. */
export function SubjectSetup({ onDone }: { onDone: () => void }) {
  useLocale()
  const input = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const [subjects, setSubjects] = useState<SubjectView[]>([])
  const [subject, setSubject] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.subjects().then(setSubjects, () => undefined)
  }, [])

  const guest = async () => {
    setBusy(true)
    setError('')
    try {
      await startDemo()
      window.location.reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : t('Please try again.'))
      setBusy(false)
    }
  }

  const pick = (list: FileList | null) => {
    const chosen = Array.from(list ?? [])
    const bad = chosen.find((f) => !/\.(pdf|txt|md)$/i.test(f.name))
    const big = chosen.find((f) => f.size > 25 * 1024 * 1024)
    setError(
      bad ? t('Choose a PDF, Markdown or text file.') : big ? t('This file is over 25 MB.') : '',
    )
    setFiles(bad || big ? [] : chosen)
    if (input.current) input.current.value = ''
  }

  const upload = async () => {
    setBusy(true)
    setError('')
    try {
      let target = subject
      if (!target && name.trim()) target = (await api.createSubject(name.trim())).subject_id
      for (const file of files) await api.uploadDocument(file, target, '', false)
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : t('Please try again.'))
      setBusy(false)
    }
  }

  return (
    <main className="solo first-visit">
      <p className="brand brand--solo">
        <span className="brand__mark" aria-hidden="true" />
        Lodestar
      </p>
      <input
        ref={input}
        type="file"
        accept=".pdf,.md,.txt"
        multiple
        hidden
        aria-label={t('Upload course files')}
        onChange={(e) => {
          pick(e.target.files)
        }}
      />
      {files.length === 0 ? (
        <section className="card setup__choice">
          <h2>{t('How do you want to start?')}</h2>
          <p className="muted">
            {t('Study from your own course chapters, or look around with a demo person first.')}
          </p>
          <button
            type="button"
            className="primary"
            disabled={busy}
            onClick={() => input.current?.click()}
          >
            {t('Import documents')}
          </button>
          <button type="button" className="ghost" disabled={busy} onClick={() => void guest()}>
            {busy ? t('Opening the demo…') : t('Explore as a guest')}
          </button>
        </section>
      ) : (
        <section className="card setup__choice">
          <h2>{t('Where do these files go?')}</h2>
          <ul className="setup__files">
            {files.map((f) => (
              <li key={f.name}>{f.name}</li>
            ))}
          </ul>
          <label>
            {t('Subject')}
            <select
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
          {!subject && (
            <input
              aria-label={t('New subject')}
              placeholder={t('e.g. C++ or Probability')}
              value={name}
              maxLength={100}
              disabled={busy}
              onChange={(e) => {
                setName(e.target.value)
              }}
            />
          )}
          <button type="button" className="primary" disabled={busy} onClick={() => void upload()}>
            {busy ? t('Uploading…') : t('Upload and start')}
          </button>
          <button
            type="button"
            className="ghost"
            disabled={busy}
            onClick={() => {
              setFiles([])
            }}
          >
            {t('Back')}
          </button>
        </section>
      )}
      {error && <p role="alert">{error}</p>}
    </main>
  )
}
