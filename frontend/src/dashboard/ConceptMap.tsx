import { useState } from 'react'

import type { ConceptStatus, CourseMapView } from '../api/types'
import { t } from '../i18n'

/** The course as a map (docs/plan/19): every concept, what it builds on (the lines), how well the
 * student knows it (the colour and the range bar), and what Lodestar noticed: a plateau, a review
 * that's due, the gap under a struggling concept. Foundations at the top, advanced at the bottom. */

const STATE: Record<ConceptStatus['state'], { label: string; tone: string; soft: string }> = {
  solid: { label: 'Solid', tone: '#15803d', soft: '#ecfdf3' },
  shaky: { label: 'Shaky', tone: '#b45309', soft: '#fff8eb' },
  struggling: { label: 'Not sticking yet', tone: '#be123c', soft: '#fff1f3' },
  not_checked: { label: 'Not checked', tone: '#64748b', soft: '#f4f6f9' },
}
const CARD_W = 232
const CARD_H = 116
const ROW_GAP = 46
const COL_GAP = 28

/** Depth = the longest chain of prerequisites under a concept. */
function depths(concepts: ConceptStatus[]): Map<string, number> {
  const out = new Map<string, number>()
  const byId = new Map(concepts.map((c) => [c.id, c]))
  const depth = (id: string): number => {
    const known = out.get(id)
    if (known !== undefined) return known
    const c = byId.get(id)
    const d = c && c.requires.length ? 1 + Math.max(...c.requires.map(depth)) : 0
    out.set(id, d)
    return d
  }
  concepts.forEach((c) => depth(c.id))
  return out
}

export function ConceptMap({
  course,
  onSelect,
}: {
  course: CourseMapView
  onSelect: (dim: string) => void
}) {
  const [now] = useState(() => Date.now())
  const d = depths(course.concepts)
  const rows: ConceptStatus[][] = []
  for (const c of course.concepts) {
    const row = d.get(c.id) ?? 0
    ;(rows[row] ??= []).push(c)
  }
  const widest = Math.max(...rows.map((r) => r.length))
  const width = widest * CARD_W + (widest - 1) * COL_GAP
  const height = rows.length * CARD_H + (rows.length - 1) * ROW_GAP
  const at = new Map<string, { x: number; y: number }>()
  rows.forEach((row, r) => {
    const rowWidth = row.length * CARD_W + (row.length - 1) * COL_GAP
    row.forEach((c, i) => {
      at.set(c.id, {
        x: (width - rowWidth) / 2 + i * (CARD_W + COL_GAP),
        y: r * (CARD_H + ROW_GAP),
      })
    })
  })
  const chain = course.gap?.chain ?? []
  const onChain = (from: string, to: string) => {
    const i = chain.indexOf(to)
    return i >= 0 && chain[i + 1] === from
  }
  const struggling = course.concepts.filter((c) => c.state === 'struggling')
  const gap = course.gap
  const name = (id: string) => course.concepts.find((c) => c.id === id)?.name ?? id
  const daysToExam = course.exam
    ? Math.max(0, Math.round((new Date(course.exam).getTime() - now) / 86_400_000))
    : null

  return (
    <div className="concept-map" data-testid="concept-map">
      <div className="concept-map__summary">
        {daysToExam !== null && (
          <p className="pill">
            <strong>{daysToExam}</strong> {t('days to the exam')}
          </p>
        )}
        <p className="pill">
          <strong>{course.concepts.filter((c) => c.state === 'solid').length}</strong>{' '}
          {t('of {n} concepts solid', { n: course.concepts.length })}
        </p>
        <p className="pill">
          <strong>{struggling.length}</strong> {t('not sticking yet')}
        </p>
      </div>
      {gap && (
        <p className="concept-map__gap" data-testid="gap-banner">
          <strong>{t('The gap:')}</strong>{' '}
          {t(
            "{concept} won't stick while {prereq}, which it builds on, is still shaky. That's where Lodestar starts.",
            { concept: name(gap.concept), prereq: name(gap.prereq).toLowerCase() },
          )}
        </p>
      )}
      {/* The map's geometry is drawn left to right in every language, so the lines meet the
          boxes; the text inside each box follows its own direction. */}
      <div className="concept-map__scroll" dir="ltr">
        <svg
          className="concept-map__lines"
          width={width}
          height={height}
          viewBox={`0 0 ${String(width)} ${String(height)}`}
          aria-hidden="true"
        >
          {course.concepts.flatMap((c) =>
            c.requires.map((r) => {
              const a = at.get(r)
              const b = at.get(c.id)
              if (!a || !b) return null
              const x1 = a.x + CARD_W / 2
              const y1 = a.y + CARD_H
              const x2 = b.x + CARD_W / 2
              const y2 = b.y
              const mid = (y1 + y2) / 2
              const hot = onChain(r, c.id)
              return (
                <path
                  key={`${r}-${c.id}`}
                  d={`M${String(x1)},${String(y1)} C${String(x1)},${String(mid)} ${String(x2)},${String(mid)} ${String(x2)},${String(y2)}`}
                  className={hot ? 'concept-line concept-line--gap' : 'concept-line'}
                />
              )
            }),
          )}
        </svg>
        <ol className="concept-map__nodes" style={{ width, height }}>
          {course.concepts.map((c) => {
            const p = at.get(c.id)
            if (!p) return null
            const s = STATE[c.state]
            return (
              <li
                key={c.id}
                style={{ left: p.x, top: p.y, width: CARD_W, height: CARD_H }}
                className={chain.includes(c.id) ? 'concept-node concept-node--gap' : 'concept-node'}
              >
                <button
                  type="button"
                  data-testid={`concept-${c.id}`}
                  style={{ borderColor: s.tone, background: s.soft }}
                  onClick={() => {
                    onSelect(c.id)
                  }}
                >
                  <span className="concept-node__top">
                    <span className="concept-node__name" dir="auto">
                      {c.name}
                    </span>
                    <span className="concept-node__section">{c.section}</span>
                  </span>
                  {c.percent !== null && c.low !== null && c.high !== null ? (
                    <span className="concept-node__value">
                      <span className="concept-range" aria-hidden="true">
                        <span
                          className="concept-range__band"
                          style={{
                            left: `${String(c.low)}%`,
                            width: `${String(Math.max(2, c.high - c.low))}%`,
                            background: s.tone,
                          }}
                        />
                        <span
                          className="concept-range__dot"
                          style={{ left: `${String(c.percent)}%`, background: s.tone }}
                        />
                      </span>
                      <span className="concept-node__pct">
                        {Math.round(c.percent)}%{' '}
                        <span className="muted">
                          ({Math.round(c.low)}–{Math.round(c.high)})
                        </span>
                      </span>
                    </span>
                  ) : (
                    <span className="concept-node__value muted small">{t('Not checked yet')}</span>
                  )}
                  <span className="concept-node__tags" dir="auto">
                    <span className="concept-tag" style={{ color: s.tone }}>
                      {t(s.label)}
                    </span>
                    {(c.blocking ?? []).length > 0 && (
                      <span className="concept-tag concept-tag--gap">
                        {t('Gap under {names}', {
                          names: (c.blocking ?? []).map((b) => name(b)).join(', '),
                        })}
                      </span>
                    )}
                    {c.plateau && (
                      <span className="concept-tag concept-tag--plateau">{t('Plateau')}</span>
                    )}
                    {c.review_due && <span className="concept-tag">{t('Review due')}</span>}
                    {c.mistakes > 0 && (
                      <span className="concept-tag" title={c.mistake ?? ''}>
                        {c.mistakes === 1 ? t('1 mix-up') : t('{n} mix-ups', { n: c.mistakes })}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      </div>
      <p className="muted small">
        {t(
          'Mastery is the chance of getting a typical question on the concept right, with its 80% range. A line means the lower concept builds on the upper one. Tap a concept for its curve, its notes and what Lodestar plans next.',
        )}
      </p>
    </div>
  )
}
