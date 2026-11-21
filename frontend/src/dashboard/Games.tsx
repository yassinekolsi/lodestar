import { useState } from 'react'

import type { Registry } from '../api/types'
import { FAMILIES } from './families'

/** The practice library (docs/plan/19): every concept of the course, by chapter, with its quiz
 * and its explain-it-back. Picking one goes to the conversation, as if the student had asked for
 * it, so Lodestar can still say if a prerequisite needs a look first. */
export function Games({ registry, onPlay }: { registry: Registry; onPlay: (ask: string) => void }) {
  const [chapter, setChapter] = useState<string | null>(null)
  const concepts = registry.dimensions.filter((d) => !d.style)
  const chapters = Object.keys(FAMILIES).filter((f) => concepts.some((c) => c.group === f))
  const shown = chapter ? concepts.filter((c) => c.group === chapter) : concepts
  const exercise = (prefix: string, dim: string) =>
    registry.games.find((g) => g.id === `${prefix}_${dim}` && g.available)

  return (
    <div className="stack" data-testid="games">
      <section className="games__library">
        <div className="games__head">
          <h2>
            {concepts.length} concepts <span className="muted">to practise</span>
          </h2>
          <div className="games__filters" role="group" aria-label="Chapter">
            <button
              type="button"
              className="chip chip--small"
              aria-pressed={chapter === null}
              onClick={() => {
                setChapter(null)
              }}
            >
              All
            </button>
            {chapters.map((f) => (
              <button
                key={f}
                type="button"
                className="chip chip--small"
                aria-pressed={chapter === f}
                onClick={() => {
                  setChapter(f)
                }}
              >
                {FAMILIES[f]?.label ?? f}
              </button>
            ))}
          </div>
        </div>
        <ul className="games__grid">
          {shown.map((c) => {
            const colour = FAMILIES[c.group] ?? { soft: '#f1f5f9', strong: '#314158' }
            const quiz = exercise('quiz', c.id)
            const explain = exercise('explain', c.id)
            return (
              <li key={c.id} className="game-card">
                <div className="game-card__top">
                  <span
                    className="game-card__badge"
                    style={{ background: colour.soft, color: colour.strong }}
                  >
                    {c.note?.match(/section (\S+)\./)?.[1] ?? c.name.slice(0, 1)}
                  </span>
                </div>
                <h3>{c.name}</h3>
                <p className="game-card__does">{c.plain}</p>
                <div className="game-card__actions">
                  {quiz && (
                    <button
                      type="button"
                      className="small"
                      onClick={() => {
                        onPlay(`play ${quiz.name}`)
                      }}
                    >
                      Quiz
                    </button>
                  )}
                  {explain && (
                    <button
                      type="button"
                      className="small"
                      onClick={() => {
                        onPlay(`play ${explain.name}`)
                      }}
                    >
                      Explain it back
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}
