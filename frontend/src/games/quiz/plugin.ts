import { button, el, itemsToTimeline, makePlugin, markAnswer } from '../../taskhost/plugin'
import type { GameModule, TrialRecord } from '../../taskhost/types'
import { scored } from '../shared/ask'
import { renderMath } from '../../lib/renderMath'
import { t } from '../../i18n'

/** One course question, as the backend serves it (backend/agent/learning.py, quiz_content). */
export interface QuizQuestion {
  id: string
  level: number
  stem: string
  options: { text: string; misconception: string | null }[]
  answer: number
  explain: string
  hints: string[]
  remove: number[]
  fixes: Record<string, { text: string; fix: string }>
}

export interface QuizContent {
  course: string
  concept: string
  concept_name: string
  section: { id: string; title: string }
  questions: QuizQuestion[]
}

interface QuizItem {
  question: QuizQuestion
  concept: string
  section: { id: string; title: string }
  number: number
  of: number
}

/** "How sure?" on every answer: a confident wrong answer is usually a misconception, an unsure
 * one is usually something not learned yet, and the coach treats them differently. */
export const SURE = [
  { label: 'Guessing', value: 0.5 },
  { label: 'Fairly sure', value: 0.75 },
  { label: 'Sure', value: 1 },
] as const

/** Course text (French for a Derja speaker) inside a right-to-left page reads left to right. */
function course<T extends HTMLElement>(node: T): T {
  node.dir = 'auto'
  return node
}

/** Waits for a click on one of the buttons (or its number key); resolves with its index. */
function pick(buttons: HTMLButtonElement[], keys: boolean): Promise<number> {
  return new Promise((resolve) => {
    const done = (i: number) => {
      document.removeEventListener('keydown', onKey)
      resolve(i)
    }
    const onKey = (e: KeyboardEvent) => {
      if (!keys) return
      const i = Number(e.key) - 1
      if (Number.isInteger(i) && i >= 0 && i < buttons.length && !buttons[i]?.disabled) done(i)
    }
    buttons.forEach((b, i) => {
      b.addEventListener('click', () => {
        done(i)
      })
    })
    document.addEventListener('keydown', onKey)
  })
}

const QuizPlugin = makePlugin<QuizItem>('lodestar-quiz', async ({ stage, item, e2e }) => {
  const q = item.question
  const head = el('p', 'quiz-head', t('Question {n} of {of}', { n: item.number, of: item.of }))
  const stem = course(el('p', 'quiz-stem', q.stem))
  stem.dataset['testid'] = 'quiz-stem'
  const options = q.options.map((o, i) => {
    const b = button(`${String(i + 1)}. ${o.text}`, `choice-${String(i)}`, 'quiz-option')
    return course(b)
  })
  const list = el('div', 'quiz-options')
  list.append(...options)
  const hintBox = course(el('p', 'quiz-hint'))
  hintBox.setAttribute('aria-live', 'polite')
  const hint = button(t('Hint'), 'quiz-hint', 'quiz-hint-button')
  const tools = el('div', 'quiz-tools')
  tools.append(hint)
  stage.append(head, stem, list, hintBox, tools)
  renderMath(stem)
  options.forEach(renderMath)
  let hints = 0
  hint.addEventListener('click', () => {
    if (hints >= q.hints.length) return
    hintBox.textContent = q.hints[hints] ?? ''
    renderMath(hintBox)
    if (hints === 1) {
      for (const i of q.remove) {
        const b = options[i]
        if (b) {
          b.disabled = true
          b.classList.add('quiz-option--gone')
        }
      }
    }
    hints += 1
    if (hints >= q.hints.length) hint.disabled = true
  })
  markAnswer(stage, e2e, `click:choice-${String(q.answer)} >> click:sure-2 >> click:quiz-next`)
  const started = performance.now()
  const choice = await pick(options, true)
  const rt = performance.now() - started
  hint.disabled = true
  options.forEach((b, i) => {
    b.disabled = true
    if (i === choice) b.classList.add('quiz-option--picked')
  })

  // How sure?
  const sureRow = el('div', 'quiz-sure')
  sureRow.append(el('span', 'quiz-sure__q', t('How sure are you?')))
  const sureButtons = SURE.map((s, i) => button(t(s.label), `sure-${String(i)}`, 'quiz-sure__b'))
  sureRow.append(...sureButtons)
  stage.append(sureRow)
  const sure = SURE[await pick(sureButtons, false)]?.value ?? 0.75
  sureRow.remove()

  // Feedback: right, or how it was wrong and the fix for that mistake.
  const correct = choice === q.answer
  const tag = q.options[choice]?.misconception ?? null
  options[q.answer]?.classList.add('quiz-option--right')
  if (!correct) options[choice]?.classList.add('quiz-option--wrong')
  const box = el('div', correct ? 'quiz-feedback quiz-feedback--right' : 'quiz-feedback')
  box.dataset['testid'] = 'quiz-feedback'
  box.append(el('p', 'quiz-feedback__title', correct ? t('Right.') : t('Not quite.')))
  const fix = tag ? q.fixes[tag] : undefined
  if (!correct && fix) {
    const m = el('p', 'quiz-feedback__misconception')
    m.dataset['testid'] = 'quiz-misconception'
    const said = el('span', '', `${fix.text}. ${fix.fix}`)
    said.dir = 'auto'
    m.append(
      el(
        'strong',
        '',
        sure >= 0.75 ? t('A common mix-up, and you were sure:') + ' ' : t('A common mix-up:') + ' ',
      ),
      said,
    )
    box.append(m)
  }
  box.append(course(el('p', 'quiz-feedback__explain', q.explain)))
  box.append(
    course(
      el(
        'p',
        'quiz-feedback__ref',
        t('Notes {id}, {title}', { id: item.section.id, title: item.section.title }),
      ),
    ),
  )
  const next = button(item.number === item.of ? t('Finish') : t('Next'), 'quiz-next', 'primary')
  box.append(next)
  stage.append(box)
  renderMath(box)
  next.focus()
  await pick([next], false)
  return {
    stimulus: {
      question_id: q.id,
      concept: item.concept,
      level: q.level,
      options: q.options.map((o) => o.text),
    },
    response: { choice, misconception: correct ? null : tag, hints },
    correct,
    rt_ms: rt,
    hint_level: hints,
    confidence: sure,
  }
})

export function metrics(trials: TrialRecord[]): Record<string, number> {
  const s = scored(trials)
  const right = s.filter((t) => t.correct === true).length
  return {
    accuracy: s.length ? right / s.length : 0,
    confident_errors: s.filter((t) => t.correct === false && (t.confidence ?? 0) >= 0.75).length,
    hints: s.reduce((a, t) => a + (t.hint_level ?? 0), 0),
  }
}

export const game: GameModule = {
  id: 'quiz',
  name: 'Quiz',
  instructions:
    'Pick the answer you think is right, then say how sure you are. A wrong answer shows how it went wrong and how to fix it. Hints are there if you need them, but an answer found with a hint counts a little less.',
  keysHint: 'Click an answer or press 1 to 4.',
  timeline({ spec, e2e }) {
    const content = spec.content as unknown as QuizContent | null
    if (!content) return []
    const items: QuizItem[] = content.questions.map((question, i) => ({
      question,
      concept: content.concept,
      section: content.section,
      number: i + 1,
      of: content.questions.length,
    }))
    // Each question carries its own confidence question, so no extra "How sure?" probes.
    return itemsToTimeline(QuizPlugin, items, 0, e2e).map((t) => ({ ...t, probe: false }))
  },
  metrics,
}
