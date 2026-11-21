import { useEffect, useRef, useState, type ReactNode } from 'react'

import { useCameraCues } from '../affect/camera'
import type { ExerciseSpec, RoundResult } from '../api/types'
import { coachSays, stopSpeaking } from '../voice/tts'
import type { GameModule, Score } from './types'
import { TaskHost, type TaskControls } from './TaskHost'
import { t } from '../i18n'

interface Props {
  spec: ExerciseSpec
  sessionId: string
  game: GameModule
  skills: string[]
  onFinish: (result: RoundResult, score: Score) => void
  reason?: ReactNode
}

/** The frame every game shares (docs/plan/06): header, stage, and pause / too hard / quit. */
export function GameFrame({ spec, sessionId, game, skills, onFinish, reason }: Props) {
  const [started, setStarted] = useState(false)
  const [paused, setPaused] = useState(false)
  const [struggling, setStruggling] = useState(false)
  const [progress, setProgress] = useState<[number, number]>([0, 0])
  const controls = useRef<TaskControls | null>(null)
  const frame = useRef<HTMLElement>(null)
  useCameraCues(started) // only with the camera switch on; frames never leave the browser

  // The game opens inside the conversation: bring it into view.
  useEffect(() => {
    frame.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  // Voice coaching (docs/plan/12): when Lodestar speaks, it reads the instructions out loud.
  useEffect(() => {
    coachSays(`${t(game.name)}. ${t(game.instructions)}`)
    return stopSpeaking
  }, [game])

  // The question on screen, not the questions finished: "2 / 5" while the second one is up,
  // the same number the exercise shows ("Question 2 of 5").
  const [done, total] = progress
  const onScreen = total ? Math.min(done + 1, total) : 0

  return (
    <section className="game-frame" aria-label={t(game.name)} ref={frame}>
      <header className="game-frame__header">
        <h2 className="game-frame__title">{t(game.name)}</h2>
        <ul className="chips" aria-label={t('Concepts')}>
          {skills.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
        {started && (
          <p className="game-frame__progress" aria-live="polite">
            {onScreen} / {total}
          </p>
        )}
      </header>
      <div className="game-frame__bar" aria-hidden="true">
        <span
          style={{
            width: `${String(progress[1] ? Math.round((progress[0] / progress[1]) * 100) : 0)}%`,
          }}
        />
      </div>

      {!started ? (
        <div className="game-frame__intro">
          {reason && <div className="game-frame__reason">{reason}</div>}
          <p className="game-frame__how">{t(game.instructions)}</p>
          <p className="game-frame__keys">{t(game.keysHint)}</p>
          {spec.practice_trials > 0 && (
            <p className="muted">{t('The first {n} are practice.', { n: spec.practice_trials })}</p>
          )}
          <button
            type="button"
            className="primary"
            onClick={() => {
              stopSpeaking()
              coachSays(t('Ready. Go!'))
              setStarted(true)
            }}
            autoFocus
          >
            {t('Start')}
          </button>
        </div>
      ) : (
        <TaskHost
          spec={spec}
          sessionId={sessionId}
          game={game}
          onFinish={onFinish}
          onProgress={(done, total) => {
            setProgress([done, total])
          }}
          onStruggle={() => {
            controls.current?.pause()
            setStruggling(true)
          }}
          controlsRef={controls}
        />
      )}

      {struggling && (
        <div
          className="game-frame__offer"
          role="dialog"
          aria-label={t('Easier?')}
          data-testid="easier-offer"
        >
          <p>{t('That looked tough. Want it a bit easier?')}</p>
          <button
            type="button"
            className="primary"
            onClick={() => {
              setStruggling(false)
              controls.current?.stop('eased')
            }}
          >
            {t('Yes, easier')}
          </button>
          <button
            type="button"
            onClick={() => {
              setStruggling(false)
              controls.current?.resume()
            }}
          >
            {t('Keep going')}
          </button>
        </div>
      )}

      {started && (
        <footer className="game-frame__footer">
          <button
            type="button"
            className="ghost small"
            onClick={() => {
              if (paused) controls.current?.resume()
              else controls.current?.pause()
              setPaused(!paused)
            }}
          >
            {paused ? t('Resume') : t('Pause')}
          </button>
          <button
            type="button"
            className="ghost small"
            onClick={() => controls.current?.stop('eased')}
          >
            {t('Too hard?')}
          </button>
          <button
            type="button"
            className="ghost small"
            onClick={() => controls.current?.stop('stopped')}
          >
            {t('Quit')}
          </button>
        </footer>
      )}
    </section>
  )
}
