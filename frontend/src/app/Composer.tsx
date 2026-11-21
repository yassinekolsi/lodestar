import { useState } from 'react'

import { Orb } from '../voice/Orb'
import type { useSession } from './useSession'
import { t, useLocale, type Locale } from '../i18n'

/** Things people often say, one tap away. Each is sent as if typed, in the student's language;
 * the router understands all three (backend/agent/intents.py). */
const STARTERS: Record<Locale, string[]> = {
  en: [
    'Something quick',
    'Quiz me on conditional probability',
    'How am I doing this week?',
    'When do I study best?',
  ],
  fr: [
    'Quelque chose de rapide',
    'Interroge-moi sur la probabilité conditionnelle',
    "Comment je m'en sors cette semaine ?",
    'Quand est-ce que je suis le plus efficace ?',
  ],
  tn: [
    'حاجة صغيرة بالزربة',
    'عطيني أسئلة على الprobabilité conditionnelle',
    'كيفاش ماشي هالجمعة ؟',
    'وقتاش نكون خير ؟',
  ],
}

/** Where you talk to Lodestar: type or tap the microphone, with a few starters. Hidden while a game
 * is running so keys go to the game. */
/** The starters for a student working from their own uploads: nothing assumes a course. */
const DOCUMENT_STARTERS: Record<Locale, string[]> = {
  en: ['Something quick', 'Quiz me on my notes', 'How am I doing this week?'],
  fr: [
    'Quelque chose de rapide',
    'Interroge-moi sur mes notes',
    "Comment je m'en sors cette semaine ?",
  ],
  tn: ['حاجة صغيرة بالزربة', 'اختبرني على الnotes متاعي', 'كيفاش ماشي هالجمعة ؟'],
}

export function Composer({
  session,
  onVoice,
  ownMaterial = false,
}: {
  session: ReturnType<typeof useSession>
  onVoice: (text: string) => void
  ownMaterial?: boolean
}) {
  const locale = useLocale()
  const { state, send, nextGame } = session
  const [text, setText] = useState('')
  const waiting = state.busy || state.phase === 'starting'
  const canPlay = state.phase === 'chatting' && !state.confirm && !state.busy
  const quiet = state.feed.length === 0 && state.phase === 'home'
  const chips = (canPlay || quiet) && (
    <div className="composer__chips">
      {canPlay && (
        <button type="button" className="chip chip--strong" onClick={() => void nextGame()}>
          {t('Another exercise')}
        </button>
      )}
      {quiet &&
        (ownMaterial ? DOCUMENT_STARTERS : STARTERS)[locale].map((s) => (
          <button
            key={s}
            type="button"
            className="chip"
            onClick={() => {
              void send(s)
            }}
          >
            {s}
          </button>
        ))}
    </div>
  )
  return (
    <div className={`composer${quiet ? ' composer--home' : ''}`}>
      {!quiet && chips}
      <form
        className="composer__box"
        onSubmit={(e) => {
          e.preventDefault()
          const said = text
          setText('')
          if (said.trim()) void send(said)
        }}
      >
        <label className="sr-only" htmlFor="say">
          {t('Say something to Lodestar')}
        </label>
        <input
          id="say"
          data-testid="say"
          value={text}
          maxLength={2000}
          autoComplete="off"
          dir="auto"
          placeholder={
            quiet
              ? t('Ask about the course, or say what you want to study')
              : t('Reply to Lodestar')
          }
          onChange={(e) => {
            setText(e.target.value)
          }}
        />
        <div className="composer__tools">
          <Orb onTranscript={onVoice} />
          <button
            type="submit"
            className="send"
            aria-label={t('Send')}
            title={t('Send')}
            disabled={!text.trim() || waiting}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>
      </form>
      {quiet && chips}
    </div>
  )
}
