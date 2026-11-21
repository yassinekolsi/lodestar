import { useEffect, useState, type ReactNode } from 'react'

import { SignalIndicator } from '../affect/SignalIndicator'
import { adoptSignIn, api, forgetUser, hasUser, inDemo } from '../api/client'
import type { Persona, Receipt } from '../api/types'
import { About } from '../dashboard/About'
import { AcsPanel } from '../dashboard/AcsPanel'
import { Agent } from '../dashboard/Agent'
import { HourHeatmap, Radar, SkillCurve, WeekHeatmap } from '../dashboard/charts'
import { Coach } from '../dashboard/Coach'
import { Experiments } from '../dashboard/Experiments'
import { Games } from '../dashboard/Games'
import { Goals } from '../dashboard/Goals'
import { Insights } from '../dashboard/Insights'
import { Memory } from '../dashboard/Memory'
import { ClassPanel } from '../dashboard/ClassPanel'
import { ConceptMap } from '../dashboard/ConceptMap'
import { Documents } from '../dashboard/Documents'
import { SkillPage } from '../dashboard/SkillPage'
import { useDashboard } from '../dashboard/useDashboard'
import { setSpeakReplies, speakReplies, stopSpeaking } from '../voice/tts'
import { useSpeakReplies } from '../voice/useSpeakReplies'
import { Composer } from './Composer'
import { Cited } from './Cited'
import { DemoToggle } from './DemoToggle'
import { PlateauToast, RushedScreen, SplitPlan } from './StressCases'
import { Conversation, Star, type Panel } from './Conversation'
import { DecisionCard } from './DecisionCard'
import { Heading } from './icons'
import { LanguagePicker } from './LanguagePicker'
import { Onboarding } from './Onboarding'
import { SubjectSetup } from './SubjectSetup'
import { Settings } from './Settings'
import { useSession } from './useSession'
import { t, useLocale } from '../i18n'

type NavItem = { id: Panel; label: string; icon: ReactNode }

/** Line icons on a 24px grid, drawn with `currentColor`. */
const PLAY: NavItem[] = [
  {
    id: 'documents',
    label: 'Documents',
    icon: <path d="M4 3h10l6 6v12H4zM14 3v6h6M8 13h8M8 17h5" />,
  },
  {
    id: 'games',
    label: 'Practice',
    icon: (
      <path d="M6 11h4M8 9v4M15 12h.01M18 10h.01M17.3 5H6.7a4 4 0 0 0-4 3.6L2 15.4A3 3 0 0 0 7.3 17.6L9 16h6l1.7 1.6a3 3 0 0 0 5.3-2.2l-.7-6.8A4 4 0 0 0 17.3 5z" />
    ),
  },
  {
    id: 'coach',
    label: 'Coach',
    icon: (
      <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01" />
    ),
  },
]
const NAV: NavItem[] = [
  {
    id: 'twin',
    label: 'Concept map',
    icon: (
      <path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3zM19 3v4M21 5h-4" />
    ),
  },
  {
    id: 'progress',
    label: 'Progress',
    icon: <path d="M3 3v16a2 2 0 0 0 2 2h16M7 15l4-4 3 3 6-6M16 8h4v4" />,
  },
  {
    id: 'insights',
    label: 'Insights',
    icon: (
      <path d="M9 18h6M10 22h4M15.1 14c.2-1 .7-1.7 1.4-2.5A6 6 0 1 0 6 8c0 1.4.5 2.5 1.5 3.5.7.7 1.2 1.5 1.4 2.5" />
    ),
  },
  {
    id: 'experiments',
    label: 'Experiments',
    icon: (
      <path d="M10 2v7.5a2 2 0 0 1-.2.9L4.7 20.6a1 1 0 0 0 .9 1.4h12.8a1 1 0 0 0 .9-1.4l-5.1-10.2a2 2 0 0 1-.2-.9V2M8.5 2h7M7 16h10" />
    ),
  },
  {
    id: 'agent',
    label: 'Agent',
    icon: (
      <path d="M12 8V4H8M6 8h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2zM2 14h2M20 14h2M15 13v2M9 13v2" />
    ),
  },
  {
    id: 'memory',
    label: 'Memory',
    icon: <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20M9 7h6M9 11h4" />,
  },
  {
    id: 'acs',
    label: 'AI collaboration',
    icon: <path d="M8 3L4 7l4 4M4 7h16M16 21l4-4-4-4M20 17H4" />,
  },
  {
    id: 'about',
    label: 'Under the hood',
    icon: <path d="M12 2l10 5-10 5L2 7zM2 17l10 5 10-5M2 12l10 5 10-5" />,
  },
]
const TEACHER: NavItem = {
  id: 'teacher',
  label: 'Class view',
  icon: (
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />
  ),
}
const SETTINGS: NavItem = {
  id: 'settings',
  label: 'Settings',
  icon: (
    <path d="M20 7h-9M14 17H5M17 20a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM7 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />
  ),
}
const ALL = [...PLAY, ...NAV, TEACHER, SETTINGS]
const SUBTITLE: Record<Panel, string> = {
  documents: 'Your subjects and chapters, with answers grounded in your own course pages.',
  games: 'A quiz and an explain-it-back for every concept of the course.',
  coach: 'Four coaches, one set of facts. Pick the voice you like.',
  insights: 'What Lodestar has learned about how you study, each with its range.',
  memory: 'What Lodestar remembers about you. Forget anything, any time.',
  about: 'The architecture, the models, how they were tested, and the rules.',
  twin: 'Every concept of the course, what it builds on, and how sure Lodestar is about you.',
  progress: 'Your exam goals and how each concept has moved.',
  experiments: 'Test one change to how you study and see if it helps you.',
  agent: 'What Lodestar did, step by step, and why.',
  acs: 'How you work with AI: checking, trying first, and taking breaks.',
  teacher: 'The whole class, as counts: what it finds hard and the mix-ups behind it.',
  settings: 'Privacy, voice, your AI provider and your data.',
}

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {children}
    </svg>
  )
}

export function App() {
  useLocale()
  const session = useSession()
  const [registered, setRegistered] = useState(() => {
    adoptSignIn()
    return hasUser()
  })
  const [panel, setPanel] = useState<Panel | null>(null)
  const [skill, setSkill] = useState<string | null>(null)
  const [why, setWhy] = useState<string | null>(null)
  const [localMode, setLocalMode] = useState(false)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [twinAsk, setTwinAsk] = useState('')
  /** Where the Twin page's own chat starts in the session feed. */
  const [twinFrom, setTwinFrom] = useState<number | null>(null)
  const dash = useDashboard(registered)
  /** A new account starts by naming a subject and importing its course files (docs/plan/20). */
  const [needsSubject, setNeedsSubject] = useState(false)
  useEffect(() => {
    if (!registered || inDemo()) return
    api.subjects().then(
      (s) => {
        setNeedsSubject(s.length === 0)
      },
      () => undefined,
    )
  }, [registered])
  const [persona, setPersona] = useState<Persona>('willow')
  // Voice in, voice out: once someone talks to Lodestar, replies are spoken too (and always shown).
  const [voiceUsed, setVoiceUsed] = useState(false)
  useSpeakReplies(session.state, persona, voiceUsed || speakReplies())
  const { registry, twin, progress, forecast, goals, acs, decisions, patterns, course } = dash

  const checkLlm = () => {
    Promise.all([api.llm(), api.consent()]).then(
      ([llm, consent]) => {
        const cloud = consent.switches.some((s) => s.id === 'cloud_ai' && s.granted)
        setLocalMode(llm.selection.mode !== 'hosted' || !cloud)
      },
      () => {
        setLocalMode(false)
      },
    )
  }

  useEffect(() => {
    if (!registered) return
    checkLlm()
    api.me().then(
      (me) => {
        setPersona(me.persona as Persona)
      },
      () => undefined,
    )
  }, [registered])

  // Escape closes the top-most popup.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (why) setWhy(null)
      else if (panel) setPanel(null)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [why, panel])

  /** A decision option ("working_memory" or "working_memory:echo") in plain words. */
  const optionName = (option: string): string => {
    const [dim = option, gameId] = option.split(':')
    const dimName = registry?.dimensions.find((d) => d.id === dim)?.name ?? dim
    const gameName = gameId ? registry?.games.find((g) => g.id === gameId)?.name : undefined
    return gameName ? `${dimName}, ${gameName}` : dimName
  }
  const dimName = (id: string) => registry?.dimensions.find((d) => d.id === id)?.name ?? id
  const playing = session.state.phase === 'playing'
  const open = (id: Panel, dim?: string) => {
    setPanel(id)
    setSkill(dim ?? null)
  }
  const tryNewFormat = (name: string) => {
    setPanel(null)
    void session.start(`Try a new format for ${name}`)
  }

  if (!registered) {
    return (
      <main className="solo">
        <p className="brand brand--solo">
          <span className="brand__mark" aria-hidden="true" />
          Lodestar
        </p>
        <LanguagePicker />
        {receipt ? (
          <section className="card" data-testid="receipt">
            <h2>{t('Everything is deleted')}</h2>
            <p>{receipt.message}</p>
            <p className="muted">
              {t('Lodestar keeps only a receipt with these counts, not who you were.')}
            </p>
            <button
              type="button"
              className="primary"
              onClick={() => {
                window.location.assign('/')
              }}
            >
              {t('Start again')}
            </button>
          </section>
        ) : (
          <Onboarding
            onDone={() => {
              setRegistered(true)
            }}
          />
        )}
      </main>
    )
  }

  if (needsSubject) {
    return (
      <SubjectSetup
        onDone={() => {
          setNeedsSubject(false)
          dash.refresh()
        }}
      />
    )
  }

  const measured = twin?.dims.filter((d) => d.n > 0) ?? []
  const current = ALL.find((n) => n.id === panel)
  const title = current ? t(current.label) : ''

  let body: ReactNode = null
  if (panel === 'twin' && registry && twin && progress) {
    body = skill ? (
      <SkillPage
        dim={skill}
        registry={registry}
        twin={twin}
        progress={progress}
        forecast={forecast}
        plateau={patterns?.plateaus.find((p) => p.dim === skill)}
        course={course}
        onTry={(p) => {
          tryNewFormat(p.name)
        }}
        onPlay={(ask) => {
          setPanel(null)
          void session.send(ask)
        }}
        onBack={() => {
          setSkill(null)
        }}
      />
    ) : (
      <>
        <section aria-label={t('Concept map')}>
          {course ? (
            <ConceptMap course={course} onSelect={setSkill} />
          ) : (
            <p className="muted">{t('Loading the course…')}</p>
          )}
        </section>
        <section className="panel-block" aria-label={t('Ask about the course')}>
          <Heading icon="chat">{t('Ask about the course')}</Heading>
          {twinFrom !== null && (
            <ul className="twin-chat" data-testid="twin-chat" aria-live="polite">
              {session.state.feed.slice(twinFrom).map((item, i) =>
                item.kind === 'you' ? (
                  <li key={i} className="twin-chat__you">
                    <p className="bubble">{item.text.replace(/^Twin, /, '')}</p>
                  </li>
                ) : item.kind === 'lodestar' ? (
                  <li
                    key={i}
                    className={`said${session.state.feed[twinFrom + i - 1]?.kind === 'lodestar' ? ' said--cont' : ''}`}
                  >
                    <Star />
                    <p>
                      <Cited text={item.text} refs={item.refs} onWhy={setWhy} />
                    </p>
                  </li>
                ) : null,
              )}
              {session.state.busy && (
                <li className="said">
                  <Star />
                  <p className="thinking">
                    <span className="thinking__dots" aria-hidden="true">
                      <i />
                      <i />
                      <i />
                    </span>
                    {t('Thinking')}
                  </p>
                </li>
              )}
            </ul>
          )}
          <form
            className="inline-ask"
            onSubmit={(e) => {
              e.preventDefault()
              const said = twinAsk.trim()
              setTwinAsk('')
              if (said) {
                if (twinFrom === null) setTwinFrom(session.state.feed.length)
                void session.send(said)
              }
            }}
          >
            <input
              value={twinAsk}
              maxLength={2000}
              placeholder={t('e.g. what is a random variable? or: what do I keep getting wrong?')}
              aria-label={t('Your question about the course')}
              onChange={(e) => {
                setTwinAsk(e.target.value)
              }}
            />
            <button type="submit" disabled={!twinAsk.trim()}>
              {t('Ask')}
            </button>
          </form>
        </section>
        <section className="panel-block">
          <Heading icon="radar">{t('All concepts at a glance')}</Heading>
          <Radar twin={twin} registry={registry} split={patterns?.split} />
          {patterns?.split && (
            <SplitPlan
              split={patterns.split}
              onPlay={() => {
                setPanel(null)
                void session.start()
              }}
            />
          )}
        </section>
      </>
    )
  } else if (panel === 'progress' && registry && twin && progress) {
    body = (
      <>
        <section className="panel-block">
          <Heading icon="target">{t('Goals')}</Heading>
          <Goals goals={goals} />
        </section>
        <section className="panel-block">
          <Heading icon="trend">{t('Each concept over time')}</Heading>
          <p className="muted small">
            {t(
              'Line: estimate. Shaded: the 80% range. Dashed: the forecast for the next sessions. Orange strips: what you told Lodestar about your days.',
            )}
          </p>
          <div className="curves">
            {measured.map((d) => (
              <div key={d.dim} className="curves__item">
                <h4>{dimName(d.dim)}</h4>
                <SkillCurve
                  twin={twin}
                  dim={d.dim}
                  forecast={forecast.find((f) => f.dim === d.dim)}
                  strips={progress.life_context}
                  name={dimName(d.dim)}
                  plateauFrom={patterns?.plateaus.find((p) => p.dim === d.dim)?.started}
                />
              </div>
            ))}
          </div>
        </section>
        <section className="panel-block">
          <Heading icon="calendar">{t('Change by week')}</Heading>
          <WeekHeatmap progress={progress} name={dimName} />
        </section>
        <section className="panel-block">
          <Heading icon="clock">{t('When you do best')}</Heading>
          <HourHeatmap progress={progress} />
        </section>
      </>
    )
  } else if (panel === 'games' && registry) {
    body = (
      <Games
        registry={registry}
        onPlay={(ask) => {
          setPanel(null)
          void session.send(ask)
        }}
      />
    )
  } else if (panel === 'coach') {
    body = <Coach onChange={setPersona} />
  } else if (panel === 'insights') {
    body = <Insights progress={progress} forecast={forecast} twin={twin} />
  } else if (panel === 'memory') {
    body = <Memory />
  } else if (panel === 'teacher') {
    body = <ClassPanel />
  } else if (panel === 'about') {
    body = <About />
  } else if (panel === 'experiments') {
    body = (
      <Experiments
        onAsk={() => {
          setPanel(null)
          void session.send('I want to run an experiment')
        }}
      />
    )
  } else if (panel === 'agent') {
    body = (
      <Agent
        timeline={session.state.timeline}
        sessionId={session.state.sessionId}
        decisions={decisions}
        name={optionName}
        onWhy={setWhy}
      />
    )
  } else if (panel === 'acs' && acs) {
    body = (
      <section className="panel-block">
        <AcsPanel acs={acs} />
      </section>
    )
  } else if (panel === 'documents') {
    body = (
      <Documents
        onAsk={(message) => {
          setPanel(null)
          void session.send(message)
        }}
      />
    )
  } else if (panel === 'settings') {
    body = (
      <Settings
        onVoiceChange={(speak) => {
          setSpeakReplies(speak)
          if (!speak) {
            setVoiceUsed(false)
            stopSpeaking()
          }
        }}
        onLlmChange={checkLlm}
        onDeleted={(r) => {
          forgetUser()
          setReceipt(r)
          setRegistered(false)
        }}
      />
    )
  }

  const navButton = (item: NavItem) => (
    <button
      key={item.id}
      type="button"
      className="rail__item"
      aria-current={panel === item.id ? 'page' : undefined}
      aria-label={t(item.label)}
      title={t(item.label)}
      onClick={() => {
        open(item.id)
      }}
    >
      <Icon>{item.icon}</Icon>
      <span className="rail__label">{t(item.label)}</span>
    </button>
  )
  const home =
    session.state.feed.length === 0 &&
    (session.state.phase === 'home' || session.state.phase === 'resumable')

  return (
    <div className={`shell${playing ? ' shell--playing' : ''}${panel ? ' shell--panel' : ''}`}>
      <aside className="rail">
        <p className="brand">
          <span className="brand__mark" aria-hidden="true" />
          <span className="brand__name">Lodestar</span>
        </p>
        <nav aria-label="Main" className="rail__nav">
          <button
            type="button"
            className="rail__item"
            aria-current={panel === null ? 'page' : undefined}
            aria-label={t('Conversation')}
            title={t('Conversation')}
            onClick={() => {
              setPanel(null)
            }}
          >
            <Icon>
              <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z" />
            </Icon>
            <span className="rail__label">{t('Conversation')}</span>
          </button>
          <p className="rail__group">{t('Study')}</p>
          {PLAY.map(navButton)}
          <p className="rail__group">{t('Your course')}</p>
          {NAV.slice(0, 4).map(navButton)}
          <p className="rail__group">{t('For teachers')}</p>
          {navButton(TEACHER)}
          <p className="rail__group">{t('Behind the scenes')}</p>
          {NAV.slice(4).map(navButton)}
          <span className="rail__spacer" />
          {localMode && (
            <p className="rail__note" title={t('Lodestar uses the model on this server')}>
              <span className="rail__dot" aria-hidden="true" />
              <span className="rail__label">{t('Local mode')}</span>
            </p>
          )}
          <LanguagePicker variant="rail" />
          <DemoToggle variant="rail" />
          {navButton(SETTINGS)}
        </nav>
      </aside>
      <SignalIndicator />

      <div className="workspace">
        <main className={`stage${home ? ' stage--home' : ''}`} hidden={panel !== null}>
          {dash.error && (
            <p role="alert" className="notice">
              {t("Couldn't load your data:")} {dash.error}
            </p>
          )}
          <Conversation
            session={session}
            registry={registry}
            twin={twin}
            goals={goals}
            progress={progress}
            setWhy={setWhy}
            onOpen={open}
            persona={persona}
          />
          {!playing && session.state.phase !== 'resumable' && (
            <Composer
              session={session}
              onVoice={(text) => {
                setVoiceUsed(true)
                void session.send(text, 'voice')
              }}
            />
          )}
        </main>

        {panel && (
          <section className="page" aria-label={title} data-panel={panel}>
            <header className="page__head">
              <div className="page__title">
                {current && (
                  <span className="page__icon">
                    <Icon>{current.icon}</Icon>
                  </span>
                )}
                <h1>{title}</h1>
              </div>
              <p className="muted">{t(SUBTITLE[panel])}</p>
            </header>
            <div className="page__body">{body ?? <p className="muted">{t('Loading…')}</p>}</div>
          </section>
        )}
      </div>

      {home && !panel && patterns?.plateaus[0] && (
        <PlateauToast
          plateau={patterns.plateaus[0]}
          onTry={(p) => {
            tryNewFormat(p.name)
          }}
          onSee={(p) => {
            open('twin', p.dim)
          }}
        />
      )}

      {session.state.rushed && (
        <RushedScreen
          card={session.state.rushed}
          sessionId={session.state.sessionId}
          onClose={session.seenRushed}
        />
      )}

      {why && (
        <div
          className="backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) setWhy(null)
          }}
        >
          <DecisionCard
            decisionId={why}
            name={optionName}
            onClose={() => {
              setWhy(null)
            }}
          />
        </div>
      )}
    </div>
  )
}
