import { useEffect, useState } from 'react'

import { api, signUp } from '../api/client'
import type { Persona, Registry } from '../api/types'
import { DemoToggle } from './DemoToggle'
import { Glyph } from './icons'
import { PERSONAS } from './personas'
import { t } from '../i18n'

type Notice = Registry['consent']

type Step = 'welcome' | 'age' | 'under' | 'consent' | 'coach'

/** First visit (UW1): what Lodestar is, the age check, consent in plain words, and a coach. Nothing
 * is stored until the last step. */
export function Onboarding({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState<Step>('welcome')
  const [notice, setNotice] = useState<Notice | null>(null)
  const [consent, setConsent] = useState<Record<string, boolean>>({})
  const [persona, setPersona] = useState<Persona>('willow')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.registry().then(
      (registry) => {
        setNotice(registry.consent)
        setConsent(Object.fromEntries(registry.consent.switches.map((s) => [s.id, s.default])))
      },
      () => {
        setError(t("Couldn't reach Lodestar. Try again in a moment."))
      },
    )
  }, [])

  const finish = async () => {
    setSaving(true)
    setError(null)
    try {
      await signUp({ consent, persona })
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setSaving(false)
    }
  }

  return (
    <section className="card onboarding" data-testid="onboarding">
      {step === 'welcome' && (
        <>
          <span className="step-icon">
            <Glyph name="star" />
          </span>
          <h2>{t('Welcome to Lodestar')}</h2>
          <p>
            {t(
              "Lodestar is a study coach for your course. It finds which concepts aren't sticking and why, explains them from your notes, quizzes you at the right level, and explains every choice it makes.",
            )}
          </p>
          <p className="muted">
            {t(
              'Lodestar measures what you know about the course, nothing else. It never labels you, and every number comes with how sure it is.',
            )}
          </p>
          <button
            type="button"
            className="primary"
            onClick={() => {
              setStep('age')
            }}
          >
            {t('Get started')}
          </button>
          <DemoToggle variant="welcome" />
        </>
      )}

      {step === 'age' && (
        <>
          <span className="step-icon">
            <Glyph name="user" />
          </span>
          <h2>{t('How old are you?')}</h2>
          <p>
            {t('This prototype is for people aged {n} and over.', {
              n: notice?.age_minimum ?? 18,
            })}
          </p>
          <div className="choice">
            <button
              type="button"
              className="primary"
              onClick={() => {
                setStep('consent')
              }}
            >
              {t("I'm {n} or older", { n: notice?.age_minimum ?? 18 })}
            </button>
            <button
              type="button"
              onClick={() => {
                setStep('under')
              }}
            >
              {t("I'm younger")}
            </button>
          </div>
        </>
      )}

      {step === 'under' && (
        <>
          <h2>{t('Not yet, sorry')}</h2>
          <p>
            {t(
              "Lodestar needs a parent or guardian's consent for younger people, and this prototype can't ask for it yet. Nothing about you has been stored.",
            )}
          </p>
        </>
      )}

      {step === 'consent' && notice && (
        <>
          <span className="step-icon">
            <Glyph name="shield" />
          </span>
          <h2>{t('What Lodestar may do')}</h2>
          <p className="muted">{t('You can change these later in Settings.')}</p>
          <ul className="switches">
            {notice.switches.map((s) => (
              <li key={s.id}>
                <label className="switch">
                  <input
                    type="checkbox"
                    checked={consent[s.id] ?? false}
                    disabled={s.required}
                    onChange={(e) => {
                      setConsent((c) => ({ ...c, [s.id]: e.target.checked }))
                    }}
                  />
                  <span>
                    <strong>{t(s.title)}</strong>
                    {s.required && <span className="muted"> {t('(needed)')}</span>}
                    <br />
                    <span className="muted">{t(s.short)}</span>
                  </span>
                </label>
                <details className="switch__more">
                  <summary>{t('Details')}</summary>
                  <p>{t(s.plain)}</p>
                </details>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="primary"
            onClick={() => {
              setStep('coach')
            }}
          >
            {t('Continue')}
          </button>
        </>
      )}

      {step === 'coach' && (
        <>
          <span className="step-icon">
            <Glyph name="smile" />
          </span>
          <h2>{t('Pick a coach')}</h2>
          <p className="muted">{t('They all say the same facts, in their own way.')}</p>
          <div className="coaches" role="radiogroup" aria-label={t('Coach')}>
            {PERSONAS.map((p) => (
              <label key={p.id} className="coach-option">
                <input
                  type="radio"
                  name="coach"
                  value={p.id}
                  checked={persona === p.id}
                  onChange={() => {
                    setPersona(p.id)
                  }}
                />
                <span>
                  <strong>{p.name}</strong> · {t(p.style)}
                  <br />
                  <span className="muted">&ldquo;{t(p.sample)}&rdquo;</span>
                </span>
              </label>
            ))}
          </div>
          <button type="button" className="primary" disabled={saving} onClick={() => void finish()}>
            {t("Let's start")}
          </button>
        </>
      )}

      {error && <p role="alert">{error}</p>}
    </section>
  )
}
