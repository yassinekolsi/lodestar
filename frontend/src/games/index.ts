import type { GameModule } from '../taskhost/types'
import { game as explain } from './explain/plugin'
import { game as quiz } from './quiz/plugin'

/** Plugins the browser can run. Course exercises name their plugin (`quiz_bayes` is played by
 * `quiz`), so every concept of every course uses the same two (docs/plan/19). */
export const GAMES: Record<string, GameModule> = Object.fromEntries(
  [quiz, explain].map((g) => [g.id, g]),
)

/** The plugin for an exercise: its `plugin` field when set, else its own id. */
export function gameFor(spec: {
  game_id: string
  plugin?: string | null | undefined
}): GameModule | undefined {
  return GAMES[spec.plugin ?? spec.game_id] ?? GAMES[spec.game_id.split('_')[0] ?? '']
}
