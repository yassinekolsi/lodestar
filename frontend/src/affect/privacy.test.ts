import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { HESITANT, STEADY, synthSpeech } from '../test/speechFixtures'
import { sendCues } from './cues'
import { BASELINE_N, finishTurn, framesFromSamples } from './voiceTone'

/** Network test (WP3.9; docs/plan/12 rule 2): while tone is read,
 * nothing at all leaves the browser; afterwards the only request is the coarse cue, one number
 * with one decimal. Every way out of the page is watched: fetch, XMLHttpRequest, WebSocket and
 * sendBeacon. */

const SESSION = '00000000-0000-4000-8000-000000000001'
const fetchSpy = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(() =>
  Promise.resolve(new Response(null, { status: 204 })),
)
const xhrSpy = vi.fn()
const wsSpy = vi.fn()
const beaconSpy = vi.fn(() => true)

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', fetchSpy)
  vi.stubGlobal('WebSocket', wsSpy)
  vi.spyOn(XMLHttpRequest.prototype, 'send').mockImplementation(xhrSpy)
  Object.defineProperty(navigator, 'sendBeacon', { value: beaconSpy, configurable: true })
  const track = { stop: vi.fn() }
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia: vi.fn(() => Promise.resolve({ getTracks: () => [track] })),
    },
  })
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
  Object.defineProperty(HTMLMediaElement.prototype, 'readyState', {
    configurable: true,
    get: () => 4,
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  fetchSpy.mockClear()
})

function requests(): { url: string; body: unknown }[] {
  return fetchSpy.mock.calls.map(([url, init]) => ({
    url,
    body: JSON.parse(init?.body as string) as unknown,
  }))
}

describe('voice tone cues (WP3.9)', () => {
  it('keeps audio and features in the browser and sends only the coarse cue', async () => {
    localStorage.clear()
    const steady = framesFromSamples(synthSpeech(STEADY))
    for (let n = 0; n < BASELINE_N; n++) finishTurn(steady, 'I think it was blue')
    const cue = finishTurn(
      framesFromSamples(synthSpeech({ ...HESITANT, seed: 7 })),
      'um so I think uh it was blue',
    )
    expect(cue).not.toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()

    await sendCues(SESSION)
    const sent = requests()
    expect(sent).toHaveLength(1)
    expect(sent[0]?.url).toBe('/api/affect/cues')
    const body = sent[0]?.body as Record<string, unknown>
    expect(Object.keys(body).sort()).toEqual(['session_id', 'voice_strain_cue'])
    expect(body['voice_strain_cue']).toBe(Math.round((cue ?? 0) * 10) / 10)
    expect(xhrSpy).not.toHaveBeenCalled()
    expect(wsSpy).not.toHaveBeenCalled()
    expect(beaconSpy).not.toHaveBeenCalled()
  })
})
