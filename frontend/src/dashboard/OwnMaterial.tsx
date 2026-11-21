import { t } from '../i18n'

/** For a student who studies their own uploads (backend/course_scope.py): the panels built on
 * the demo's course (concept map, practice library, class view) point to what works instead,
 * their documents and quizzes made from them. */
export function OwnMaterial({
  what,
  onDocuments,
  onAsk,
}: {
  what: 'map' | 'practice' | 'class'
  onDocuments: () => void
  onAsk: (message: string) => void
}) {
  const lede = {
    map: t(
      'The concept map is drawn from a course with its concepts and prerequisites. You study from your own documents, so ask about them or take a quiz made from their pages.',
    ),
    practice: t(
      'Your practice comes from your own documents: every question is made from one of your pages and cites it.',
    ),
    class: t(
      'The class view counts a whole class on the same course. Your account studies its own documents, so there is no class to show yet.',
    ),
  }[what]
  return (
    <section className="card own-material" data-testid="own-material">
      <p>{lede}</p>
      <div className="actions">
        <button
          type="button"
          className="primary"
          onClick={() => {
            onAsk(t('Quiz me on my notes'))
          }}
        >
          {t('Quiz me on my notes')}
        </button>
        <button type="button" onClick={onDocuments}>
          {t('Open Documents')}
        </button>
      </div>
    </section>
  )
}
