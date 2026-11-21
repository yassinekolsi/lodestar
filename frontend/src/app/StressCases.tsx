import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { CourseText } from '../lib/math'
import { t } from '../i18n'
import type {
  AgentCard,
  DocumentSource,
  PlateauView,
  SplitView,
  WhyLine,
  WidenedRange,
} from '../api/types'

/** What each stress case looks like on screen. Each has its own colour, so it can't be mistaken
 * for another: red for a rushed round, amber for a plateau, blue for "why", violet for pushback,
 * teal for a forecast, green and orange for a split profile's two tracks. */

export function WhyLines({ lines }: { lines: WhyLine[] }) {
  if (lines.length === 0) return null
  return (
    <ul className="why-lines" data-testid="why-lines">
      {lines.map((line) => (
        <li key={line.source}>
          <span className="why-lines__source">{line.source}</span>
          {line.text}
        </li>
      ))}
    </ul>
  )
}

const TRACK: Record<string, { label: string; tone: string }> = {
  advanced: { label: 'Advanced track', tone: 'advanced' },
  foundation: { label: 'Foundation track', tone: 'foundation' },
  new_format: { label: 'New format', tone: 'plateau' },
}

export function TrackTag({ track, level }: { track: string; level: number }) {
  const shown = TRACK[track]
  if (!shown) return null
  return (
    <span className={`stress-tag stress-tag--${shown.tone}`} data-testid="track-tag">
      {t(shown.label)}
      {track !== 'new_format' &&
        ` · ${t('level {n}/10', { n: Math.max(1, Math.round(level * 10)) })}`}
    </span>
  )
}

/** Two ranges on one 0-100 track: what it was, what it is now. */
function RangeChange({ item }: { item: WidenedRange }) {
  return (
    <li className="range-change">
      <p>
        <strong>{item.name}</strong>{' '}
        <span className="muted">
          {t('stays at {value}%, range {low}-{high}% →', {
            value: item.value,
            low: item.before_low,
            high: item.before_high,
          })}{' '}
          <strong>
            {item.after_low}-{item.after_high}%
          </strong>
        </span>
      </p>
      <div className="range-change__track" aria-hidden="true">
        <span
          className="range-change__after"
          style={{
            left: `${String(item.after_low)}%`,
            width: `${String(item.after_high - item.after_low)}%`,
          }}
        />
        <span
          className="range-change__before"
          style={{
            left: `${String(item.before_low)}%`,
            width: `${String(item.before_high - item.before_low)}%`,
          }}
        />
        <span className="range-change__dot" style={{ left: `${String(item.value)}%` }} />
      </div>
    </li>
  )
}

const ANSWERS = [
  ['rushing', 'I was rushing'],
  ['distracted', 'I got distracted'],
  ['testing', 'I was just trying it out'],
] as const

/** The button masher: a full red screen as soon as the round ends. It didn't count, the estimate
 * didn't drop, and Lodestar asks what happened instead of assuming. */
export function RushedScreen({
  card,
  sessionId,
  onClose,
}: {
  card: Extract<AgentCard, { card: 'rushed' }>
  sessionId: string | null
  onClose: () => void
}) {
  const [answer, setAnswer] = useState<string | null>(null)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])
  const reply = (value: string) => {
    setAnswer(value)
    if (sessionId)
      void api
        .label({ session_id: sessionId, kind: 'rushed', value, round_id: card.round_id })
        .catch(() => undefined)
  }
  return (
    <div
      className="rushed"
      role="alertdialog"
      aria-label={t('Round not counted')}
      data-testid="rushed"
    >
      <div className="rushed__body">
        <p className="rushed__flag">
          {t('Round flagged')} · {card.game}
        </p>
        <h2>{t("That round didn't count")}</h2>
        <p className="rushed__lede">
          {t(
            "Those answers came too fast to tell me anything about you, so I'm not treating it as a drop in skill.",
          )}
        </p>
        <ul className="rushed__stats">
          {card.median_rt_ms !== null && (
            <li>
              <strong>{card.median_rt_ms} ms</strong>
              <span>{t('typical answer')}</span>
            </li>
          )}
          {card.answered > 0 && (
            <li>
              <strong>
                {card.correct}/{card.answered}
              </strong>
              <span>{t('right')}</span>
            </li>
          )}
          <li>
            <strong>0</strong>
            <span>{t('points of change to your estimate')}</span>
          </li>
        </ul>
        {card.dims.length > 0 && (
          <>
            <p className="rushed__note">{t("Instead, I'm less sure about you for now:")}</p>
            <ul className="rushed__ranges">
              {card.dims.map((d) => (
                <RangeChange key={d.name} item={d} />
              ))}
            </ul>
          </>
        )}
        {answer === null ? (
          <>
            <p className="rushed__ask">{t('What happened?')}</p>
            <div className="rushed__actions">
              {ANSWERS.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => {
                    reply(value)
                  }}
                >
                  {t(label)}
                </button>
              ))}
            </div>
          </>
        ) : (
          <>
            <p className="rushed__ask">
              {t('Thanks, noted. Take a breath; the next one can count.')}
            </p>
            <div className="rushed__actions">
              <button type="button" onClick={onClose} autoFocus data-testid="rushed-close">
                {t('Back to Lodestar')}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

/** The plateau, as a popup on the conversation. Dismissed for this browser tab. */
export function PlateauToast({
  plateau,
  onTry,
  onSee,
}: {
  plateau: PlateauView
  onTry: (p: PlateauView) => void
  onSee: (p: PlateauView) => void
}) {
  const [closed, setClosed] = useState(false)
  if (closed) return null
  return (
    <aside className="toast stress stress--plateau" role="status" data-testid="plateau-toast">
      <p className="stress-tag stress-tag--plateau">{t('Plateau spotted')}</p>
      <p>
        <strong>{plateau.name}</strong>{' '}
        {t('has stayed near {value}% (likely {low}-{high}%) for {days} days of practice.', {
          value: Math.round(plateau.percent),
          low: Math.round(plateau.low),
          high: Math.round(plateau.high),
          days: plateau.days,
        })}
      </p>
      {plateau.game_name && (
        <p className="muted small">
          {t('Next, try a new format: {name}.', { name: plateau.game_name })}
        </p>
      )}
      <div className="actions">
        <button
          type="button"
          className="primary"
          onClick={() => {
            onTry(plateau)
          }}
        >
          {t('Try a new format')}
        </button>
        <button
          type="button"
          onClick={() => {
            onSee(plateau)
          }}
        >
          {t('See the curve')}
        </button>
        <button
          type="button"
          className="ghost"
          aria-label={t('Dismiss')}
          onClick={() => {
            setClosed(true)
          }}
        >
          {t('Not now')}
        </button>
      </div>
    </aside>
  )
}

/** The same plateau on the skill's own page, with the change of approach. */
export function PlateauNote({
  plateau,
  onTry,
}: {
  plateau: PlateauView
  onTry?: ((p: PlateauView) => void) | undefined
}) {
  return (
    <div className="stress stress--plateau" data-testid="plateau-note">
      <p className="stress-tag stress-tag--plateau">
        {t('Plateau · {days} days', { days: plateau.days })}
      </p>
      <p>
        {t(
          "Your estimate has stayed near {value}% (likely {low}-{high}%) over {answers} answers. More of the same probably won't move it, so I'll change things.",
          {
            value: Math.round(plateau.percent),
            low: Math.round(plateau.low),
            high: Math.round(plateau.high),
            answers: plateau.answers,
          },
        )}
      </p>
      {plateau.game_name && (
        <p>
          <strong>{t('New format:')}</strong> {plateau.game_name}
          {plateau.same_skill ? '.' : t(', from the same family of skills.')}
        </p>
      )}
      <p>
        <strong>{t('New approach:')}</strong> {plateau.strategy}
      </p>
      {onTry && (
        <button
          type="button"
          className="primary"
          onClick={() => {
            onTry(plateau)
          }}
        >
          {t('Try a new format')}
        </button>
      )}
    </div>
  )
}

/** A split profile: two tracks, each at its own level, never one average difficulty. */
export function SplitPlan({ split, onPlay }: { split: SplitView; onPlay: () => void }) {
  const sides = [split.advanced, split.foundation]
  return (
    <div className="stress stress--split" data-testid="split-plan">
      <p className="stress-tag stress-tag--split">
        {t('Split profile · {gap} points apart', { gap: Math.round(split.gap) })}
      </p>
      <p>
        {t(
          "These two concepts are far apart, so I don't use one difficulty for both. Exercises take turns between two tracks.",
        )}
      </p>
      <div className="split-tracks">
        {sides.map((side) => (
          <article
            key={side.dim}
            className={`split-track split-track--${side.track}`}
            data-track={side.track}
          >
            <p className="split-track__kind">
              {side.track === 'advanced'
                ? `▲ ${t('Advanced track')}`
                : `▼ ${t('Foundation track')}`}
            </p>
            <h4>{side.name}</h4>
            <p className="muted small">
              {t('{value}%, likely {low}-{high}%', {
                value: Math.round(side.percent),
                low: Math.round(side.low),
                high: Math.round(side.high),
              })}
            </p>
            <div className="range-bar" aria-hidden="true">
              <span
                className="range-bar__band"
                style={{
                  left: `${String(side.low)}%`,
                  width: `${String(side.high - side.low)}%`,
                }}
              />
              <span className="range-bar__dot" style={{ left: `${String(side.percent)}%` }} />
            </div>
            <p>
              <strong>
                {t('Level {n} of 10', { n: Math.max(1, Math.round(side.level * 10)) })}
              </strong>
              {t(', aiming for {p}% right', { p: Math.round(side.target_p * 100) })}
            </p>
            {side.game_name && (
              <p className="muted small">{t('Next up: {name}', { name: side.game_name })}</p>
            )}
          </article>
        ))}
      </div>
      <button type="button" className="primary" onClick={onPlay}>
        {t('Play this plan')}
      </button>
    </div>
  )
}

function Sources({ sources }: { sources: DocumentSource[] }) {
  return (
    <div aria-label={t('Course sources')}>
      {sources.map((source, i) => (
        <details
          className="documents__passage"
          key={`${source.title}-${String(source.page)}-${String(i)}`}
        >
          <summary dir="auto">
            {source.title} · {t('page {n}', { n: source.page })}
          </summary>
          <div>
            <CourseText text={source.text} />
          </div>
        </details>
      ))}
    </div>
  )
}

/** The cards the agent adds to the conversation. */
export function AgentCardView({
  card,
  onWhy,
}: {
  card: Exclude<AgentCard, { card: 'rushed' }>
  onWhy: (decisionId: string) => void
}) {
  switch (card.card) {
    case 'sources':
      return (
        <article className="turn-card stress" data-testid="sources-card">
          <p className="eyebrow">{t('From your course pages')}</p>
          <p dir="auto">{card.question.replace(/\s*\[document:[^\]]+\]/g, '')}</p>
          <Sources sources={card.sources} />
        </article>
      )
    case 'lesson':
      return (
        <article className="turn-card stress stress--lesson" data-testid="lesson-card">
          <p className="stress-tag stress-tag--lesson">
            {t('From your notes')} ·{' '}
            <bdi>
              {card.section_id} {card.section_title}
            </bdi>
          </p>
          <div className="lesson-passage" dir="auto">
            <CourseText text={card.passage} />
          </div>
          <div className="lesson-facts">
            {card.sources && <Sources sources={card.sources} />}
            {card.mastery && (
              <p>
                <strong>{t('Where you are:')}</strong>{' '}
                {t('{value}% (likely {low}-{high}%)', {
                  value: card.mastery.now,
                  low: card.mastery.low,
                  high: card.mastery.high,
                })}
              </p>
            )}
            {card.mistake && (
              <p data-testid="lesson-mistake">
                <strong>
                  {t('Your usual mix-up ({count} times):', { count: card.mistake.count })}
                </strong>{' '}
                <bdi>
                  {card.mistake.text}. {card.mistake.fix}
                </bdi>
              </p>
            )}
            {card.gap && (
              <p data-testid="lesson-gap">
                <strong>{t('Builds on {name}', { name: card.gap.name.toLowerCase() })}</strong>
                {card.gap.now === null
                  ? t(', which I haven’t checked yet.')
                  : t(', still shaky: {now}% (likely {low}-{high}%). Notes {section}.', {
                      now: String(card.gap.now),
                      low: String(card.gap.low),
                      high: String(card.gap.high),
                      section: card.gap.section,
                    })}
              </p>
            )}
          </div>
        </article>
      )
    case 'mistakes':
      return (
        <article className="turn-card stress stress--mistakes" data-testid="mistakes-card">
          <p className="stress-tag stress-tag--mistakes">
            {t('The mix-ups behind your wrong answers')}
          </p>
          <ol className="mistake-list">
            {card.rows.map((r) => (
              <li key={`${r.dim}-${r.text}`}>
                <p>
                  <strong dir="auto">{r.text}</strong>{' '}
                  <span className="muted small">
                    <bdi>{r.concept}</bdi> · {t('{n} times', { n: r.count })}
                    {r.confident > 0 ? ` · ${t('{n} while sure', { n: r.confident })}` : ''}
                  </span>
                </p>
                <p className="mistake-fix" dir="auto">
                  {r.fix}
                </p>
              </li>
            ))}
          </ol>
        </article>
      )
    case 'why':
      return (
        <article className="turn-card stress stress--why" data-testid="why-card-inline">
          <p className="stress-tag stress-tag--why">
            {t('The data behind my pick')} · {card.when}
          </p>
          {card.lines.length === 0 && <p>{card.reason}</p>}
          <WhyLines lines={card.lines} />
          <button
            type="button"
            className="link"
            onClick={() => {
              onWhy(card.decision_id)
            }}
          >
            {t('See every option I weighed')}
          </button>
        </article>
      )
    case 'history':
      return (
        <article className="turn-card stress stress--why" data-testid="history-card">
          <p className="stress-tag stress-tag--why">{t('Your history')}</p>
          <table className="history-table">
            <tbody>
              {card.rows.map((r, i) => (
                <tr key={i}>
                  <td className="muted">{r.day}</td>
                  <td>{r.game}</td>
                  <td>
                    {r.score === null ? t('not counted') : t('{n}% right', { n: String(r.score) })}
                  </td>
                  <td>
                    {r.decision_id && (
                      <button
                        type="button"
                        className="link"
                        onClick={() => {
                          if (r.decision_id) onWhy(r.decision_id)
                        }}
                      >
                        {t('Why?')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      )
    case 'forecast':
      return (
        <article className="turn-card stress stress--forecast" data-testid="forecast-card">
          <p className="stress-tag stress-tag--forecast">{t('A range, not a promise')}</p>
          <p className="muted small">
            {t(
              'If you keep your current pace ({n} more sessions). No single number: every forecast is an 80% range.',
              { n: card.sessions },
            )}
          </p>
          <ul className="forecast-rows">
            {card.rows.map((r) => (
              <li key={r.name}>
                <p>
                  <strong>{r.name}</strong>{' '}
                  <span className="muted">
                    {t('likely {low}–{high}%', { low: r.low, high: r.high })}
                  </span>
                </p>
                <div className="forecast-rows__track" aria-hidden="true">
                  <span
                    className="forecast-rows__now"
                    style={{
                      left: `${String(r.now_low)}%`,
                      width: `${String(r.now_high - r.now_low)}%`,
                    }}
                  />
                  <span
                    className="forecast-rows__then"
                    style={{ left: `${String(r.low)}%`, width: `${String(r.high - r.low)}%` }}
                  />
                </div>
                <p className="muted small">
                  {t('Today {low}-{high}%', { low: r.now_low, high: r.now_high })}
                </p>
              </li>
            ))}
          </ul>
          {card.held !== null && (
            <p className="muted small">
              {t('Ranges like these held {n}% of the time on real learners the model never saw.', {
                n: card.held,
              })}
            </p>
          )}
        </article>
      )
    case 'pushback':
      return (
        <article className="turn-card stress stress--pushback" data-testid="pushback-card">
          <p className="stress-tag stress-tag--pushback">
            {t('Pushback accepted')} · {card.game}
          </p>
          <ul className="rushed__ranges">
            {card.dims.map((d) => (
              <RangeChange key={d.name} item={d} />
            ))}
          </ul>
          {card.acs_after !== null && (
            <p>
              <strong>{t('AI Collaboration Score')}</strong>{' '}
              {card.acs_before !== null && <span className="muted">{card.acs_before} → </span>}
              <strong>{card.acs_after}</strong>{' '}
              <span className="muted">
                {t('(likely {low}-{high}). Critical verification and iteration both went up.', {
                  low: String(card.acs_low),
                  high: String(card.acs_high),
                })}
              </span>
            </p>
          )}
        </article>
      )
  }
}
