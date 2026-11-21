import { button, el, makePlugin, markAnswer } from '../../taskhost/plugin'
import type { GameModule, TrialRecord } from '../../taskhost/types'
import { voiceAnswer } from '../../voice/answer'
import { scored } from '../shared/ask'

/** Explain it back, as the backend serves it (backend/agent/learning.py, explain_content). */
export interface ExplainContent {
  course: string
  concept: string
  concept_name: string
  section: { id: string; title: string }
  prompt: string
  key_ideas: { text: string; words: string[] }[]
}

const ENOUGH_WORDS = 25

/** The rubric, the same rule as backend/agent/learning.py (rubric_score): a key idea counts when
 * at least half its words appear (first five letters, so "multiply" matches "multiplying"),
 * scaled down for very short answers. A plain rule, so it counts at low weight (reliability 0.4)
 * and the student sees exactly which ideas it found. */
export function rubric(
  text: string,
  ideas: ExplainContent['key_ideas'],
): { score: number; hits: boolean[] } {
  const words = text.toLowerCase().match(/[a-z]+/g) ?? []
  const found = new Set(words.map((w) => w.slice(0, 5)))
  const hits = ideas.map((idea) => {
    const need = Math.max(1, Math.floor((idea.words.length + 1) / 2))
    return idea.words.filter((w) => found.has(w)).length >= need
  })
  const share = ideas.length ? hits.filter(Boolean).length / ideas.length : 0
  const length = (text.match(/\w+/g) ?? []).length
  return { score: share * Math.min(1, length / ENOUGH_WORDS), hits }
}

const ExplainPlugin = makePlugin<ExplainContent>(
  'lodestar-explain',
  async ({ stage, item, e2e }) => {
    stage.append(el('p', 'quiz-head', `Explain it back: ${item.concept_name}`))
    stage.append(el('p', 'quiz-stem', item.prompt))
    const input = el('textarea', 'ml-input explain-input')
    input.dataset['testid'] = 'recall-input'
    input.setAttribute('aria-label', 'Your explanation')
    input.placeholder = 'In your own words, with one example'
    const say = voiceAnswer(input, 'Say it', (a) => a.transcript, 90_000)
    const done = button('Done', 'recall-done', 'primary')
    const row = el('div', 'type-row')
    row.append(say.button, done)
    stage.append(input, row)
    markAnswer(
      stage,
      e2e,
      `type:${item.key_ideas.map((i) => i.text).join('. ')} >> click:recall-done`,
    )
    input.focus()
    const started = performance.now()
    await new Promise<void>((resolve) => {
      done.addEventListener('click', () => {
        resolve()
      })
    })
    say.cancel()
    const rt = performance.now() - started
    const { score, hits } = rubric(input.value, item.key_ideas)
    input.disabled = true
    row.remove()

    const box = el('div', 'quiz-feedback quiz-feedback--right')
    box.dataset['testid'] = 'explain-feedback'
    const got = hits.filter(Boolean).length
    box.append(
      el(
        'p',
        'quiz-feedback__title',
        `You covered ${String(got)} of the ${String(hits.length)} key ideas.`,
      ),
    )
    const list = el('ul', 'explain-ideas')
    item.key_ideas.forEach((idea, i) => {
      const li = el('li', hits[i] ? 'explain-idea explain-idea--hit' : 'explain-idea', idea.text)
      list.append(li)
    })
    box.append(list)
    if (got < hits.length) {
      box.append(
        el(
          'p',
          'quiz-feedback__ref',
          `The ones without a tick are worth a second look: Notes ${item.section.id}, ${item.section.title}.`,
        ),
      )
    }
    const next = button('Finish', 'quiz-next', 'primary')
    box.append(next)
    stage.append(box)
    await new Promise<void>((resolve) => {
      next.addEventListener('click', () => {
        resolve()
      })
    })
    return {
      stimulus: { concept: item.concept, ideas: item.key_ideas.length },
      response: {
        score,
        covered: item.key_ideas.filter((_, i) => hits[i]).map((idea) => idea.text),
        words: (input.value.match(/\w+/g) ?? []).length,
        text: input.value.slice(0, 2000),
      },
      correct: null,
      rt_ms: rt,
    }
  },
)

export function metrics(trials: TrialRecord[]): Record<string, number> {
  const s = scored(trials)
  const scores = s.map((t) => Number(t.response?.['score'] ?? 0))
  return { rubric_score: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0 }
}

export const game: GameModule = {
  id: 'explain',
  name: 'Explain it back',
  instructions:
    'Explain the idea in your own words, as if to a classmate. Lodestar checks which key ideas you covered and shows you the ones you missed.',
  keysHint: 'Type or say your explanation, then Done.',
  timeline({ spec, e2e }) {
    const content = spec.content as unknown as ExplainContent | null
    if (!content) return []
    return [
      {
        type: ExplainPlugin,
        item: content,
        trial_index: 0,
        practice: false,
        e2e,
        probe: false,
      },
    ]
  },
  metrics,
}
