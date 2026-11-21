import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import { parse } from 'yaml'

import { GAMES, gameFor } from './index'

test('every course concept is played by a plugin the browser has', () => {
  const dir = join(import.meta.dirname, '../../../registry/courses')
  const courses = readdirSync(dir)
    .filter((f) => f.endsWith('.yaml'))
    .map((f) => parse(readFileSync(join(dir, f), 'utf8')) as { concepts: { id: string }[] })
  expect(courses.length).toBeGreaterThan(0)
  for (const course of courses) {
    for (const c of course.concepts) {
      expect(gameFor({ game_id: `quiz_${c.id}`, plugin: 'quiz' })).toBe(GAMES['quiz'])
      expect(gameFor({ game_id: `explain_${c.id}` })).toBe(GAMES['explain'])
    }
  }
})
