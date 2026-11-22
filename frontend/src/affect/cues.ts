import { api } from '../api/client'

/** Optional strain cue (docs/plan/12; WP3.9 voice tone). Audio and tone features stay in this
 * browser: the only thing that leaves it is one coarse number (0 to 1, one decimal), sent with
 * the next round and only with the voice tone switch on. */
export type CueSignal = 'voice'

const latest: Record<CueSignal, number | null> = { voice: null }
const stoppers = new Map<CueSignal, () => void>()
const listeners = new Set<() => void>()
let snapshot: readonly CueSignal[] = []

function changed(): void {
  snapshot = [...stoppers.keys()]
  for (const listener of listeners) listener()
}

/** One decimal: "possible strain: 0.4", never anything finer. */
export function coarse(value: number): number {
  return Math.round(Math.min(1, Math.max(0, value)) * 10) / 10
}

export function recordCue(signal: CueSignal, value: number): void {
  latest[signal] = coarse(value)
}

/** A signal in use registers how to stop it; the on-screen indicator lists these. */
export function signalStarted(signal: CueSignal, stop: () => void): void {
  stoppers.set(signal, stop)
  changed()
}

export function signalStopped(signal: CueSignal): void {
  if (stoppers.delete(signal)) changed()
}

export function stopSignal(signal: CueSignal): void {
  stoppers.get(signal)?.()
  signalStopped(signal)
}

export function activeSignals(): readonly CueSignal[] {
  return snapshot
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Send the latest cues, if any, then forget them. A failure only loses the cue. */
export async function sendCues(sessionId: string): Promise<void> {
  if (latest.voice === null) return
  const body = { session_id: sessionId, voice_strain_cue: latest.voice }
  latest.voice = null
  try {
    await api.cues(body)
  } catch {
    // switch turned off meanwhile, or offline: behaviour alone decides
  }
}
