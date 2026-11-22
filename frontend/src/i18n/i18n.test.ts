import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { afterEach, describe, expect, it } from 'vitest'

import { FR } from './fr'
import { getLocale, setLocale, t } from './index'
import { TN } from './tn'

const SRC = join(__dirname, '..')

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === 'i18n' ? [] : sources(path)
    return /\.tsx?$/.test(name) && !name.includes('.test.') ? [path] : []
  })
}

/** Every literal passed to t(...) in the app. */
function literalKeys(): string[] {
  const call = /\bt\(\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")/g
  const keys = new Set<string>()
  for (const file of sources(SRC)) {
    for (const m of readFileSync(file, 'utf8').matchAll(call)) {
      const raw = m[1] ?? ''
      keys.add(raw.slice(1, -1).replace(/\\'/g, "'").replace(/\\"/g, '"'))
    }
  }
  return [...keys]
}

/** Text that reaches t() through a variable: tables of labels, the exercise modules, the coach
 * personas and the consent notice (registry/consent.yaml). */
const INDIRECT = [
  'Good morning',
  'Good afternoon',
  'Good evening',
  'Documents',
  'Practice',
  'Coach',
  'Concept map',
  'Progress',
  'Insights',
  'Experiments',
  'Agent',
  'Memory',
  'AI collaboration',
  'Under the hood',
  'Class view',
  'Settings',
  'Quiz',
  'Explain it back',
  'Guessing',
  'Fairly sure',
  'Sure',
  'Solid',
  'Shaky',
  'Not sticking yet',
  'Not checked',
  'Advanced track',
  'Foundation track',
  'New format',
  'I was rushing',
  'I got distracted',
  'I was just trying it out',
  'Chapter 1 · Counting and events',
  'Chapter 2 · Conditional probability',
  'Chapter 3 · Random variables',
  'Chapter 4 · Continuous distributions',
  'A calm mentor',
  'An energetic trainer',
  'A factual analyst',
  'A casual friend',
  'Core practice data',
  'Cloud AI',
  'Microphone',
  'Voice tone',
  'Research export',
]

afterEach(() => {
  setLocale('en')
})

describe('translations', () => {
  const keys = [...literalKeys(), ...INDIRECT]

  it('finds the strings the app translates', () => {
    expect(keys.length).toBeGreaterThan(250)
    expect(keys).toContain('Start studying')
  })

  it.each([
    ['French', FR],
    ['Derja', TN],
  ])('%s has every string', (_, table) => {
    const missing = keys.filter((k) => !(k in table))
    expect(missing).toEqual([])
  })

  it.each([
    ['French', FR],
    ['Derja', TN],
  ])('%s keeps every {placeholder}', (_, table) => {
    const broken = Object.entries(table).filter(([en, tr]) => {
      const want = (en.match(/\{\w+\}/g) ?? []).sort().join()
      return (tr.match(/\{\w+\}/g) ?? []).sort().join() !== want
    })
    expect(broken).toEqual([])
  })

  it('writes Derja in Arabic script, not in Latin letters only', () => {
    const latinOnly = Object.entries(TN).filter(
      ([en, tr]) => /[a-z]{4}/i.test(en) && !/[؀-ۿ]/.test(tr) && tr === en,
    )
    // Product names and terms kept in French are fine; whole sentences left in English are not.
    expect(latinOnly.filter(([en]) => en.includes(' ')).map(([en]) => en)).toEqual([])
  })
})

describe('t', () => {
  it('falls back to English and fills placeholders', () => {
    expect(getLocale()).toBe('en')
    expect(t('Question {n} of {of}', { n: 2, of: 5 })).toBe('Question 2 of 5')
    expect(t('Something nobody translated')).toBe('Something nobody translated')
  })

  it('switches language and sets the page direction', () => {
    setLocale('fr')
    expect(t('Start studying')).toBe('Commencer à étudier')
    expect(document.documentElement.dir).toBe('ltr')
    setLocale('tn')
    expect(t('Question {n} of {of}', { n: 2, of: 5 })).toBe('السؤال 2 من 5')
    expect(document.documentElement.dir).toBe('rtl')
    expect(document.documentElement.lang).toBe('ar-TN')
  })
})
