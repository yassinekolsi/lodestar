import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { ClassView } from '../api/types'
import { t } from '../i18n'

/** The teacher's view (docs/plan/19): the whole class as counts and medians, never names. What
 * the class finds hard, the mix-ups behind it, and who has gone quiet, so the next lecture can
 * start where the class actually is. */
export function ClassPanel() {
  const [view, setView] = useState<ClassView | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    api.classView().then(setView, (e: unknown) => {
      setError(e instanceof Error ? e.message : String(e))
    })
  }, [])
  if (error) return <p role="alert">{error}</p>
  if (!view) return <p className="muted">{t('Loading the class…')}</p>
  const hardest = [...view.concepts]
    .filter((c) => c.students > 0)
    .sort((a, b) => b.struggling / b.students - a.struggling / a.students)

  return (
    <div className="stack class-view" data-testid="class-view">
      <ul className="pills" aria-label={t('The class')}>
        <li>
          <strong>{view.students}</strong> {t('students')}
        </li>
        <li>
          <strong>{view.active_week}</strong> {t('studied this week')}
        </li>
        <li>
          <strong>{view.drifting}</strong> {t('gone quiet')}
        </li>
      </ul>

      {view.suggestions.length > 0 && (
        <section className="panel-block" aria-label={t('What to revisit in class')}>
          <h3>{t('What to revisit in class')}</h3>
          <ul className="class-suggestions" data-testid="class-suggestions">
            {view.suggestions.map((s) => (
              <li key={s} dir="auto">
                {s}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel-block" aria-label={t('Concepts')}>
        <h3>{t('Where the class is, concept by concept')}</h3>
        <table className="class-table">
          <thead>
            <tr>
              <th>{t('Concept')}</th>
              <th>{t('Median mastery')}</th>
              <th>{t('Not sticking')}</th>
              <th>{t('Solid')}</th>
            </tr>
          </thead>
          <tbody>
            {hardest.map((c) => (
              <tr key={c.id}>
                <td dir="auto">
                  {c.name} <span className="muted small">{c.section}</span>
                </td>
                <td>
                  <span className="class-bar" aria-hidden="true">
                    <span style={{ width: `${String(c.median_percent ?? 0)}%` }} />
                  </span>{' '}
                  {c.median_percent === null ? '–' : `${String(Math.round(c.median_percent))}%`}
                </td>
                <td>{t('{n} of {total}', { n: c.struggling, total: c.students })}</td>
                <td>{c.solid}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel-block" aria-label={t('Mix-ups')}>
        <h3>{t('The mix-ups behind wrong answers')}</h3>
        <ol className="mistake-list">
          {view.mistakes.map((m) => (
            <li key={`${m.concept}-${m.id}`}>
              <p>
                <strong dir="auto">{m.text}</strong>{' '}
                <span className="muted small">
                  <bdi>{m.concept_name}</bdi> · {t('{n} students', { n: m.students })} ·{' '}
                  {t('{n} answers', { n: m.count })} ·{' '}
                  {t('{n}% while sure', {
                    n: Math.round((100 * m.confident) / Math.max(1, m.count)),
                  })}
                </span>
              </p>
              <p className="mistake-fix" dir="auto">
                {m.fix}
              </p>
            </li>
          ))}
        </ol>
      </section>
      <p className="muted small">
        {t(
          "Counts only: no names and no single student's answers. In a school deployment this page is for the course's teachers.",
        )}
      </p>
    </div>
  )
}
