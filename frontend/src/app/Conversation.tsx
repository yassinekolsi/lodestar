import { useEffect, useRef, useState, type ReactNode } from 'react'

import { api } from '../api/client'
import type { GoalView, Persona, ProgressView, Registry, TwinView } from '../api/types'
import { Goals } from '../dashboard/Goals'
import { NightSky } from '../dashboard/NightSky'
import { gameFor } from '../games'
import { GameFrame } from '../taskhost/GameFrame'
import { Cited } from './Cited'
import { Glyph } from './icons'
import { PERSONAS } from './personas'
import { AgentCardView, WhyLines, TrackTag } from './StressCases'
import type { FeedItem, Surface, useSession } from './useSession'
import { greeting, t, useLocale } from '../i18n'

export type Panel =
  | 'documents'
  | 'games'
  | 'coach'
  | 'twin'
  | 'progress'
  | 'insights'
  | 'experiments'
  | 'agent'
  | 'memory'
  | 'acs'
  | 'about'
  | 'teacher'
  | 'settings'

/** `?ask=...` starts the session with that request, as if the user had said it. */
function askFromUrl(): string | undefined {
  const ask = new URLSearchParams(window.location.search).get('ask')
  return ask?.trim() ? ask.trim() : undefined
}

/** Things to try on the home screen. Each is sent as typed, so each one is written the way a
 * student would ask it in that language; the router understands all three (backend/agent/intents). */
const ASKS: Record<'en' | 'fr' | 'tn', string[]> = {
  en: [
    'Quiz me on my notes',
    "I don't get Bayes' theorem",
    'Why did you pick my last exercise?',
    'What exactly will my Bayes score be next month?',
    "That wasn't fair, the room was noisy",
  ],
  fr: [
    'Interroge-moi sur mes notes',
    'Je ne comprends pas le théorème de Bayes',
    'Pourquoi tu as choisi mon dernier exercice ?',
    'Quel sera exactement mon score en Bayes le mois prochain ?',
    "C'est pas juste, il y avait du bruit",
  ],
  tn: [
    'اختبرني على الnotes متاعي',
    'ما فهمتش théorème de Bayes',
    'علاش اخترت التمرين اللي فات ؟',
    'ma fhemtech el probabilité conditionnelle',
    'موش عادل، كان فما حس برشا',
  ],
}

export function Star({ size = 32 }: { size?: number }) {
  return (
    <span className="avatar" aria-hidden="true" style={{ width: size, height: size }}>
      <svg viewBox="0 0 24 24" width={size * 0.55} height={size * 0.55}>
        <path d="M12 1.5l2.6 7.9 7.9 2.6-7.9 2.6L12 22.5l-2.6-7.9L1.5 12l7.9-2.6z" />
      </svg>
    </span>
  )
}

function AfterGameLabels({
  sessionId,
  roundId,
  monitor,
}: {
  sessionId: string
  roundId: string | null
  monitor: { decisionId: string; chosen: string } | null
}) {
  const [mood, setMood] = useState<string | null>(null)
  const [answered, setAnswered] = useState(false)
  const send = (kind: 'mood' | 'was_i_right', value: string, extra: object) => {
    void api.label({ session_id: sessionId, kind, value, ...extra }).catch(() => undefined)
  }
  const guessed = monitor && (monitor.chosen === 'ease' || monitor.chosen === 'break')
  return (
    <div className="labels">
      <div className="mood" role="group" aria-label={t('Mood')}>
        <span className="labels__ask">{t('How did that feel?')}</span>
        {(
          [
            ['good', `😀 ${t('Good')}`],
            ['ok', `😐 ${t('OK')}`],
            ['tough', `😣 ${t('Tough')}`],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className="chip chip--small"
            aria-pressed={mood === value}
            disabled={mood !== null}
            onClick={() => {
              setMood(value)
              send('mood', value, roundId ? { round_id: roundId } : {})
            }}
          >
            {label}
          </button>
        ))}
      </div>
      {guessed && !answered && (
        <p className="was-i-right">
          {t('I thought that one was hard for you. Was I right?')}{' '}
          <button
            type="button"
            className="chip chip--small"
            onClick={() => {
              setAnswered(true)
              send('was_i_right', 'yes', { decision_id: monitor.decisionId })
            }}
          >
            {t('Yes')}
          </button>{' '}
          <button
            type="button"
            className="chip chip--small"
            onClick={() => {
              setAnswered(true)
              send('was_i_right', 'no', { decision_id: monitor.decisionId })
            }}
          >
            {t('No')}
          </button>
        </p>
      )}
    </div>
  )
}

/** A surface the agent opened beside its reply: a glance, with a way into the full panel. */
function SurfaceCard({
  what,
  dim,
  registry,
  twin,
  goals,
  progress,
  onOpen,
}: {
  what: Surface
  dim: string | null
  registry: Registry | null
  twin: TwinView | null
  goals: GoalView[]
  progress: ProgressView | null
  onOpen: (panel: Panel, dim?: string) => void
}) {
  const [experiments, setExperiments] = useState<Awaited<ReturnType<typeof api.experiments>>>([])
  useEffect(() => {
    if (what === 'experiments') api.experiments().then(setExperiments, () => undefined)
  }, [what])

  let body: ReactNode = null
  let open: { label: string; panel: Panel } = { label: t('Open'), panel: 'twin' }
  if (what === 'twin' && registry && twin) {
    body = (
      <NightSky
        registry={registry}
        dims={twin.dims}
        compact
        testId="night-sky-inline"
        onSelect={(d) => {
          onOpen('twin', d)
        }}
      />
    )
    open = { label: dim ? t('See this concept') : t('See every concept'), panel: 'twin' }
  } else if (what === 'goals') {
    body = <Goals goals={goals} testId="goals-inline" />
    open = { label: t('Open charts'), panel: 'progress' }
  } else if (what === 'progress' && progress) {
    body = (
      <ul className="stats">
        <li>
          <strong>{progress.stats.streak_days}</strong>
          <span>{t('day streak')}</span>
        </li>
        <li>
          <strong>{progress.stats.rounds_this_week}</strong>
          <span>{t('exercises this week')}</span>
        </li>
        <li>
          <strong>
            {progress.stats.skills_measured}/{progress.stats.skills_total}
          </strong>
          <span>{t('concepts checked')}</span>
        </li>
      </ul>
    )
    open = { label: t('Open charts'), panel: 'progress' }
  } else if (what === 'experiments') {
    body =
      experiments.length === 0 ? (
        <p className="muted">{t('No experiments yet.')}</p>
      ) : (
        <ul className="lines">
          {experiments.slice(0, 3).map((e) => (
            <li key={e.exp_id}>
              <strong>{e.hypothesis}</strong>{' '}
              <span className="muted">
                ·{' '}
                {Object.entries(e.progress)
                  .map(([c, n]) => `${c} ${String(n)}/${String(e.sessions_per_condition)}`)
                  .join(', ')}
              </span>
            </li>
          ))}
        </ul>
      )
    open = { label: t('Open the lab'), panel: 'experiments' }
  }
  if (!body) return null
  const title = {
    twin: t('Your concepts'),
    goals: t('Goals'),
    progress: t('Your week'),
    experiments: t('Lab'),
  }[what]
  return (
    <article className="turn-card surface" data-surface={what}>
      <header className="turn-card__head">
        <p className="eyebrow">{title}</p>
        <button
          type="button"
          className="ghost small"
          onClick={() => {
            onOpen(open.panel, what === 'twin' && dim ? dim : undefined)
          }}
        >
          {open.label} ↗
        </button>
      </header>
      {body}
    </article>
  )
}

/** The conversation with Lodestar, which is the whole app: Lodestar talks, and games, results and the
 * Twin open right here in the thread (docs/plan/03). Panels hold the long-form views. */
export function Conversation({
  session,
  registry,
  twin,
  goals,
  progress,
  setWhy,
  onOpen,
  persona = 'willow',
}: {
  persona?: Persona
  session: ReturnType<typeof useSession>
  registry: Registry | null
  twin: TwinView | null
  goals: GoalView[]
  progress: ProgressView | null
  setWhy: (decisionId: string) => void
  onOpen: (panel: Panel, dim?: string) => void
}) {
  const locale = useLocale()
  const { state, start, answer, play, finish, resumeSaved, skipSaved } = session
  const coach = PERSONAS.find((p) => p.id === persona) ?? {
    name: 'Lodestar',
    icon: 'star' as const,
    soft: '#f1f5f9',
    strong: '#020618',
  }
  const end = useRef<HTMLDivElement>(null)
  const now = new Date()

  // Follow the conversation as it grows.
  const size = state.feed.length + (state.confirm ? 1 : 0) + (state.busy ? 1 : 0)
  useEffect(() => {
    // A game scrolls itself into view instead.
    if (size > 0 && state.phase !== 'playing')
      end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [size, state.phase])

  const skillNames = (gameId: string): string[] => {
    const g = registry?.games.find((x) => x.id === gameId)
    if (!g || !registry) return []
    return Object.keys(g.dims).map((d) => registry.dimensions.find((x) => x.id === d)?.name ?? d)
  }
  const livePick = state.spec
    ? state.feed.findLastIndex((i) => i.kind === 'pick' && i.spec.round_id === state.spec?.round_id)
    : -1
  const liveResult = ['scoring', 'after', 'ended'].includes(state.phase)
    ? state.feed.findLastIndex((i) => i.kind === 'result')
    : -1
  const lastLodestar = state.feed.findLast((i) => i.kind === 'lodestar')
  const heroShown =
    state.feed.length === 0 && (state.phase === 'home' || state.phase === 'resumable')

  const render = (item: FeedItem, i: number): ReactNode => {
    switch (item.kind) {
      case 'you':
        return <p className="bubble">{item.text}</p>
      case 'lodestar':
        return (
          <div className="said">
            <Star />
            <p>
              <Cited text={item.text} refs={item.refs} onWhy={setWhy} />
            </p>
          </div>
        )
      case 'pick': {
        const game = gameFor(item.spec)
        const name =
          registry?.games.find((g) => g.id === item.spec.game_id)?.name ??
          game?.name ??
          item.spec.game_id
        if (i !== livePick) {
          const played = state.feed.some(
            (x) => x.kind === 'result' && x.roundId === item.spec.round_id,
          )
          // A played round shows as its result card; only skipped offers leave a line.
          if (played) return null
          return (
            <p className="record">
              <span className="record__mark" aria-hidden="true" />
              {t('Offered')} <strong>{name}</strong>
            </p>
          )
        }
        if (state.phase === 'playing' && state.sessionId && game)
          return (
            <GameFrame
              key={item.spec.round_id}
              spec={item.spec}
              sessionId={state.sessionId}
              game={game}
              skills={skillNames(item.spec.game_id)}
              reason={
                <>
                  {item.spec.track && <TrackTag track={item.spec.track} level={item.spec.level} />}
                  <span>{item.spec.reason}</span>
                  <WhyLines lines={item.spec.why ?? []} />
                </>
              }
              onFinish={finish}
            />
          )
        return (
          <article className="pick" data-testid="suggestion">
            <div className="pick__body">
              <p className="pick__meta">
                {state.phase === 'after' ? t('Up next') : t('Your exercise')}
              </p>
              <h2>{name}</h2>
              {typeof item.spec.content?.['concept_name'] === 'string' && (
                <p className="muted">
                  {t('From {name}', { name: item.spec.content['concept_name'] })}
                </p>
              )}
              {game && <p className="pick__how">{t(game.instructions)}</p>}
              <div className="why-box" data-testid="why-box">
                <p className="why-box__title">
                  {t('Why this exercise')}
                  {item.spec.track ? ' ' : ''}
                  {item.spec.track && <TrackTag track={item.spec.track} level={item.spec.level} />}
                </p>
                <p className="reason">
                  <span className="reason__text">{item.reason ?? item.spec.reason}</span>
                  {item.decision && (
                    <button
                      type="button"
                      className="link"
                      onClick={() => {
                        if (item.decision) setWhy(item.decision)
                      }}
                    >
                      {t('See every option')}
                    </button>
                  )}
                </p>
                <WhyLines lines={item.spec.why ?? []} />
              </div>
            </div>
            {game ? (
              <button type="button" className="primary pick__go" onClick={play}>
                {state.phase === 'after' ? t('Next exercise') : t("Let's go")}
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            ) : (
              <p role="alert">{t("This exercise isn't ready in the browser yet.")}</p>
            )}
          </article>
        )
      }
      case 'result': {
        const live = i === liveResult
        const gameId =
          item.gameId ??
          state.feed.findLast(
            (x): x is Extract<FeedItem, { kind: 'pick' }> =>
              x.kind === 'pick' && x.spec.round_id === item.roundId,
          )?.spec.game_id
        const gameName = gameId
          ? (registry?.games.find((g) => g.id === gameId)?.name ?? gameId)
          : t('Round')
        const dims = gameId
          ? Object.keys(registry?.games.find((g) => g.id === gameId)?.dims ?? {})
          : []
        const views = dims
          .map((d) => twin?.dims.find((v) => v.dim === d && v.n > 0))
          .filter((v) => v !== undefined)
        // Fact lines (with citations) sit behind "How I worked this out"; story and encouragement
        // lines stay in view.
        const story = item.says.filter((l) => !/\[[FDKM]\d+\]/.test(l.text))
        const facts = item.says.filter((l) => /\[[FDKM]\d+\]/.test(l.text))
        return (
          <article
            className={`result${live ? ' result--live' : ''}${item.flagged ? ' result--flagged' : ''}`}
            data-testid={live ? 'after-game' : undefined}
          >
            <div className="result__head">
              <span className="result__check" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d={item.flagged ? 'M6 6l12 12M18 6L6 18' : 'M5 12.5l4.5 4.5L19 7.5'} />
                </svg>
              </span>
              <p className="result__game">{gameName}</p>
              {item.flagged && (
                <span className="stress-tag stress-tag--rushed" data-testid="not-counted">
                  {t('Not counted')}
                </span>
              )}
              {item.score && item.score.total > 0 && (
                <p className="result__score">
                  <strong>{item.score.right}</strong>
                  <span>{t('/ {total} right', { total: item.score.total })}</span>
                </p>
              )}
            </div>
            {live && views.length > 0 && (
              <ul className="result__skills">
                {views.map((v) => (
                  <li key={v.dim}>
                    <span>{registry?.dimensions.find((d) => d.id === v.dim)?.name ?? v.dim}</span>
                    <strong>{Math.round(v.percent)}%</strong>
                    <span className="muted">
                      {t('likely {low}–{high}%', {
                        low: Math.round(v.percent_low),
                        high: Math.round(v.percent_high),
                      })}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div className="coach" data-testid={live ? 'coach' : undefined}>
              {live && (
                <p className="coach__who">
                  <span
                    className="coach__face"
                    style={{ background: coach.soft, color: coach.strong }}
                    aria-hidden="true"
                  >
                    <Glyph name={coach.icon} />
                  </span>
                  <strong>{coach.name}</strong>
                  <span className="muted">{t('your coach')}</span>
                </p>
              )}
              {item.says.length === 0 && live && (
                <p className="muted thinking">{t('Looking at your answers')}</p>
              )}
              {!item.flagged && facts[0] && (
                <p className="coach__main">
                  <Cited text={facts[0].text} refs={facts[0].refs} onWhy={setWhy} />
                </p>
              )}
              {story.map((line, j) => (
                <p key={j} className={item.flagged && j === 0 ? 'coach__main' : undefined}>
                  <Cited text={line.text} refs={line.refs} onWhy={setWhy} />
                </p>
              ))}
              {item.flagged && facts[0] && (
                <p>
                  <Cited text={facts[0].text} refs={facts[0].refs} onWhy={setWhy} />
                </p>
              )}
              {facts.length > 1 && (
                <details className="result__more">
                  <summary>{t('How I worked this out')}</summary>
                  {facts.slice(1).map((line, j) => (
                    <p key={j}>
                      <Cited text={line.text} refs={line.refs} onWhy={setWhy} />
                    </p>
                  ))}
                </details>
              )}
            </div>
            {live && state.sessionId && item.says.length > 0 && (
              <AfterGameLabels
                key={state.lastRoundId ?? 'none'}
                sessionId={state.sessionId}
                roundId={state.lastRoundId}
                monitor={state.lastMonitor}
              />
            )}
          </article>
        )
      }
      case 'show':
        return (
          <SurfaceCard
            what={item.what}
            dim={item.dim}
            registry={registry}
            twin={twin}
            goals={goals}
            progress={progress}
            onOpen={onOpen}
          />
        )
      case 'card':
        return <AgentCardView card={item.card} onWhy={setWhy} />
      case 'ended':
        return (
          <article className="turn-card ended">
            <p className="eyebrow">{t('Session done')}</p>
            <p>{t("Nice work. Come back whenever you like; I'll pick up from here.")}</p>
            {i === state.feed.length - 1 && state.phase === 'ended' && (
              <button type="button" className="primary" onClick={() => void start()}>
                {t('Start another session')}
              </button>
            )}
          </article>
        )
    }
  }

  return (
    <section className="thread" data-testid="chat" aria-label={t('Talk to Lodestar')}>
      {heroShown ? (
        <header className="hero">
          <span className="hero__orb" aria-hidden="true" />
          <h1>{greeting(now)}</h1>
          <p className="hero__lede">
            {t(
              "I'm Lodestar, your study coach. Bring your C++, probability or other course notes. I help you understand the ideas, check what sticks, and work through the mix-ups behind your answers.",
            )}
          </p>
          {progress && (
            <ul className="pills" aria-label={t('Your week')}>
              <li>
                <strong>{progress.stats.streak_days}</strong> {t('day streak')}
              </li>
              <li>
                <strong>{progress.stats.rounds_this_week}</strong> {t('exercises this week')}
              </li>
              <li>
                <strong>
                  {progress.stats.skills_measured}/{progress.stats.skills_total}
                </strong>{' '}
                {t('concepts checked')}
              </li>
            </ul>
          )}
          {state.phase === 'home' && (
            <div className="hero__actions" data-testid="start">
              <button
                type="button"
                className="action"
                onClick={() => {
                  onOpen('documents')
                }}
              >
                <span className="action__title">{t('Upload your course')}</span>
                <span className="action__text">
                  {t('Add subjects and chapters, then learn from your own pages')}
                </span>
              </button>
              <button
                type="button"
                className="action action--primary"
                onClick={() => void start(askFromUrl())}
              >
                <span className="action__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M7 4.5v15l12-7.5z" />
                  </svg>
                </span>
                <span className="action__title">{t('Start studying')}</span>
                <span className="action__text">
                  {t('The concept that needs you most, at your level')}
                </span>
              </button>
              <button
                type="button"
                className="action"
                title={t('The mix-ups behind your wrong answers, and the fix for each')}
                onClick={() => void start(t('What do I keep getting wrong?'))}
              >
                <span className="action__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5" />
                  </svg>
                </span>
                <span className="action__title">{t('My mistakes')}</span>
                <span className="action__text">
                  {t('What I keep getting wrong, and how to fix it')}
                </span>
              </button>
            </div>
          )}
          {state.phase === 'home' && (
            <div className="ask-chips" aria-label={t('Try asking')}>
              <span className="muted small">{t('Try asking')}</span>
              {ASKS[locale].map((ask) => (
                <button
                  key={ask}
                  type="button"
                  className="chip chip--small"
                  onClick={() => void start(ask)}
                >
                  {ask}
                </button>
              ))}
            </div>
          )}
        </header>
      ) : (
        <h1 className="sr-only">Lodestar</h1>
      )}

      <ol className="feed">
        {state.feed.map((item, i) => {
          const node = render(item, i)
          if (node === null) return null
          return (
            <li
              key={i}
              className={`feed__item feed__item--${item.kind}${item.kind === 'lodestar' && state.feed[i - 1]?.kind === 'lodestar' ? ' feed__item--cont' : ''}${i === livePick && state.phase === 'playing' ? ' feed__item--playing' : ''}`}
            >
              {node}
            </li>
          )
        })}
      </ol>

      {state.phase === 'resumable' && state.spec && (
        <article className="turn-card" data-testid="resume">
          <p className="eyebrow">{t('Welcome back')}</p>
          <p>
            {t('You were in the middle of {name}. Resume or skip?', {
              name:
                registry?.games.find((g) => g.id === state.spec?.game_id)?.name ??
                state.spec.game_id,
            })}
          </p>
          <div className="actions">
            <button type="button" className="primary" onClick={() => void resumeSaved()}>
              {t('Resume')}
            </button>
            <button type="button" onClick={() => void skipSaved()}>
              {t('Skip')}
            </button>
          </div>
        </article>
      )}

      {state.confirm && (
        <article
          className="turn-card confirm"
          role="dialog"
          aria-label={t('Lodestar asks')}
          data-testid="confirm"
        >
          <div className="said">
            <Star />
            <p>
              <Cited text={state.confirm.prompt} />
            </p>
          </div>
          <div className="actions">
            <button type="button" className="primary" onClick={() => void answer(true)}>
              {t('Yes')}
            </button>
            <button type="button" onClick={() => void answer(false)}>
              {t('No')}
            </button>
          </div>
        </article>
      )}

      {(state.busy || state.phase === 'starting') && (
        <div className="said said--busy">
          <Star />
          <p className="thinking">
            <span className="thinking__dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            {state.phase === 'starting' && state.feed.length <= 1
              ? t('Choosing your first exercise')
              : t('Thinking')}
          </p>
        </div>
      )}

      {state.phase === 'error' && (
        <p role="alert" className="turn-card">
          {t("Couldn't reach Lodestar:")} {state.error}
        </p>
      )}

      <p className="sr-only" aria-live="polite">
        {lastLodestar?.kind === 'lodestar' ? lastLodestar.text : ''}
      </p>
      <div ref={end} className="thread__end" />
    </section>
  )
}
