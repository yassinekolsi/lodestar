import type {
  CourseMapView,
  ForecastView,
  PlateauView,
  ProgressView,
  Registry,
  TwinView,
} from '../api/types'
import { PlateauNote } from '../app/StressCases'
import { SkillCurve } from './charts'
import { t } from '../i18n'

/** One concept (docs/plan/19): what it is, the notes on it, its key ideas, the student's mastery
 * with its curve, what it builds on, and a quiz or an explain-it-back one tap away. */
export function SkillPage({
  dim,
  registry,
  twin,
  progress,
  forecast,
  plateau,
  course,
  onTry,
  onPlay,
  onBack,
}: {
  dim: string
  registry: Registry
  twin: TwinView
  progress: ProgressView
  forecast: ForecastView[]
  plateau?: PlateauView | undefined
  course?: CourseMapView | null
  onTry?: (plateau: PlateauView) => void
  onPlay?: (ask: string) => void
  onBack: () => void
}) {
  const def = registry.dimensions.find((d) => d.id === dim)
  if (!def) return null
  const view = twin.dims.find((d) => d.dim === dim && d.n > 0)
  const band = forecast.find((f) => f.dim === dim)
  const concept = course?.concepts.find((c) => c.id === dim)
  const section = course?.sections.find((s) => s.id === concept?.section)
  const name = (id: string) => course?.concepts.find((c) => c.id === id)?.name ?? id
  return (
    <section className="card skill" data-testid="skill-page">
      <button type="button" className="link" onClick={onBack}>
        {t('← Back to the concept map')}
      </button>
      <h2>{def.name}</h2>
      <p>{def.plain}.</p>
      {view ? (
        <p className={view.still_learning ? 'muted' : ''}>
          {t('Mastery')} {Math.round(view.percent)}
          {t('%, likely')} {Math.round(view.percent_low)}-{Math.round(view.percent_high)}
          {t('%: the chance of getting a typical question on it right')}
          {view.still_learning ? '. Still learning about you.' : '.'}
        </p>
      ) : (
        <p className="muted">{t('Not checked yet.')}</p>
      )}
      {concept && concept.requires.length > 0 && (
        <p className="muted">
          {t('Builds on')} {concept.requires.map(name).join(', ').toLowerCase()}.
        </p>
      )}
      {concept?.mistake && (
        <p data-testid="concept-mistake">
          <strong>
            {t('Your usual mix-up (')}
            {concept.mistakes} {t('times):')}
          </strong>{' '}
          {concept.mistake}
        </p>
      )}
      {onPlay && (
        <div className="game-card__actions">
          <button
            type="button"
            className="primary"
            onClick={() => {
              onPlay(`play Quiz: ${def.name}`)
            }}
          >
            {t('Quiz me')}
          </button>
          <button
            type="button"
            onClick={() => {
              onPlay(`play Explain it back: ${def.name}`)
            }}
          >
            {t('Explain it back')}
          </button>
        </div>
      )}
      {plateau && <PlateauNote plateau={plateau} onTry={onTry} />}
      <SkillCurve
        twin={twin}
        dim={dim}
        forecast={band}
        strips={progress.life_context}
        name={def.name}
        plateauFrom={plateau?.started}
      />
      {band && (
        <p className="muted small">
          {t('Forecast after')} {band.sessions_ahead} {t('more sessions:')}{' '}
          {Math.round(band.median)}
          {t('%, likely')} {Math.round(band.low)}-{Math.round(band.high)}%. {band.note}
        </p>
      )}
      {section && (
        <>
          <h3>
            {t('From your notes ·')} {section.id} {section.title}
          </h3>
          <div className="lesson-passage">
            {section.text
              .trim()
              .split('\n')
              .map((line, i) => (
                <p key={i}>{line}</p>
              ))}
          </div>
        </>
      )}
      {concept && (
        <>
          <h3>{t('Key ideas')}</h3>
          <ul className="lines">
            {concept.key_ideas.map((k) => (
              <li key={k}>{k}</li>
            ))}
          </ul>
        </>
      )}
      <h3>{t('What can bias it')}</h3>
      <p className="muted">{def.biases.join(' ')}</p>
    </section>
  )
}
