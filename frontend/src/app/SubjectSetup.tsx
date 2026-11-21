import { Documents } from '../dashboard/Documents'
import { t, useLocale } from '../i18n'

/** Use the same upload, progress and review flow on first visit and in the library. */
export function SubjectSetup({
  onDone,
  onAsk,
}: {
  onDone: () => void
  onAsk: (message: string) => void
}) {
  useLocale()
  return (
    <main className="library-setup">
      <div className="documents__actions library-setup__heading">
        <strong>Lodestar</strong>
        <button onClick={onDone}>{t('Start studying')}</button>
      </div>
      <Documents onAsk={onAsk} />
    </main>
  )
}
