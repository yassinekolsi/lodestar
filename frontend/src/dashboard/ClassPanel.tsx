import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { ClassView } from '../api/types'

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
  if (!view) return <p className="muted">Loading the class…</p>
  const hardest = [...view.concepts]
    .filter((c) => c.students > 0)
    .sort((a, b) => b.struggling / b.students - a.struggling / a.students)

  return (
    <div className="stack class-view" data-testid="class-view">
      <ul className="pills" aria-label="The class">
        <li>
          <strong>{view.students}</strong> students
        </li>
        <li>
          <strong>{view.active_week}</strong> studied this week
        </li>
        <li>
          <strong>{view.drifting}</strong> gone quiet
        </li>
      </ul>

      {view.suggestions.length > 0 && (
        <section className="panel-block" aria-label="What to revisit">
          <h3>What to revisit in class</h3>
          <ul className="class-suggestions" data-testid="class-suggestions">
            {view.suggestions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel-block" aria-label="Concepts">
        <h3>Where the class is, concept by concept</h3>
        <table className="class-table">
          <thead>
            <tr>
              <th>Concept</th>
              <th>Median mastery</th>
              <th>Not sticking</th>
              <th>Solid</th>
            </tr>
          </thead>
          <tbody>
            {hardest.map((c) => (
              <tr key={c.id}>
                <td>
                  {c.name} <span className="muted small">{c.section}</span>
                </td>
                <td>
                  <span className="class-bar" aria-hidden="true">
                    <span style={{ width: `${String(c.median_percent ?? 0)}%` }} />
                  </span>{' '}
                  {c.median_percent === null ? '–' : `${String(Math.round(c.median_percent))}%`}
                </td>
                <td>
                  {c.struggling} of {c.students}
                </td>
                <td>{c.solid}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel-block" aria-label="Mix-ups">
        <h3>The mix-ups behind wrong answers</h3>
        <ol className="mistake-list">
          {view.mistakes.map((m) => (
            <li key={`${m.concept}-${m.id}`}>
              <p>
                <strong>{m.text}</strong>{' '}
                <span className="muted small">
                  {m.concept_name} · {m.students} students · {m.count} answers ·{' '}
                  {Math.round((100 * m.confident) / Math.max(1, m.count))}% while sure
                </span>
              </p>
              <p className="mistake-fix">{m.fix}</p>
            </li>
          ))}
        </ol>
      </section>
      <p className="muted small">
        Counts only: no names and no single student&apos;s answers. In a school deployment this page
        is for the course&apos;s teachers.
      </p>
    </div>
  )
}
