import { useState } from 'react'

import { api } from '../api/client'
import { Documents } from '../dashboard/Documents'
import { t, useLocale } from '../i18n'
import { DemoToggle } from './DemoToggle'

/** First visit: import a chapter, or explore the demo. Studying needs a document of one's own,
 * so "Start studying" stays closed until there is one. */
export function SubjectSetup({
  onDone,
  onAsk,
}: {
  onDone: () => void
  onAsk: (message: string) => void
}) {
  useLocale()
  const [blocked, setBlocked] = useState(false)
  const start = async () => {
    const docs = await api.documents().catch(() => [])
    if (docs.length > 0) onDone()
    else setBlocked(true)
  }
  return (
    <main className="library-setup">
      <div className="documents__actions library-setup__heading">
        <p className="brand">
          <span className="brand__mark" aria-hidden="true" />
          <span className="brand__name">Lodestar</span>
        </p>
        <button type="button" onClick={() => void start()}>
          {t('Start studying')}
        </button>
      </div>
      <p className="library-setup__choice">
        {t(
          'Import a chapter of your course to study from it, or explore Lodestar as a demo person.',
        )}
      </p>
      <DemoToggle variant="welcome" />
      {blocked && <p role="alert">{t('Import a chapter first, or explore the demo.')}</p>}
      <Documents onAsk={onAsk} />
    </main>
  )
}
