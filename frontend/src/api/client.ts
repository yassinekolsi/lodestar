import type {
  AgentEvent,
  AcsView,
  ClassView,
  ConsentView,
  CourseMapView,
  Decision,
  DocumentView,
  SubjectView,
  PassageView,
  ExperimentView,
  ForecastView,
  PatternsView,
  InsightsView,
  GoalView,
  KeySaved,
  LlmOverview,
  LlmSelection,
  MeView,
  ModelCard,
  MyData,
  Persona,
  ProgressView,
  Receipt,
  TraceRow,
  Registry,
  TrialEvent,
  TwinView,
} from './types'

import { getLocale, t } from '../i18n'

const TOKEN_KEY = 'lodestar.token'
export const API_BASE = '/api'
/** The language the backend answers in (backend/i18n.py). WebSockets pass it as `?lang=`. */
export const LOCALE_HEADER = 'X-Lodestar-Locale'
export const withLang = (url: string): string =>
  `${url}${url.includes('?') ? '&' : '?'}lang=${getLocale()}`

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Private mode: the token lives only in memory for this page.
  }
}

let memoryToken: string | null = null

/** The code `lodestar login` asks for: this browser's sign-in token (UW19). */
export function signInCode(): string | null {
  return memoryToken ?? getToken()
}

/** A demo token can go stale (the demo person was seeded again). Every panel would then fail
 * with "Unknown token"; instead, fetch one fresh demo token (shared by concurrent requests) and
 * retry once. */
let demoRefresh: Promise<void> | null = null

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  try {
    return await send<T>(path, init)
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 401 || path === '/demo' || !inDemo()) throw e
    demoRefresh ??= startDemo().finally(() => {
      demoRefresh = null
    })
    await demoRefresh
    return send<T>(path, init)
  }
}

async function send<T>(path: string, init: RequestInit): Promise<T> {
  const token = memoryToken ?? getToken()
  const headers = new Headers(init.headers)
  if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  headers.set(LOCALE_HEADER, getLocale())
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!response.ok) {
    let detail =
      response.status >= 500
        ? t('The server is temporarily unavailable. Please try again shortly.')
        : response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** `?signin=<token>` (printed by `make seed`) signs this browser in as that user once, then the
 * token leaves the address bar. For the demo user; everyone else signs up through the first-visit
 * screens. */
export function adoptSignIn(): void {
  const url = new URL(window.location.href)
  const token = url.searchParams.get('signin')
  if (!token) return
  memoryToken = token
  setToken(token)
  url.searchParams.delete('signin')
  window.history.replaceState(null, '', url.toString())
}

export function hasUser(): boolean {
  return Boolean(memoryToken ?? getToken())
}

/** The token of the user who went through the first-visit screens. */
export function ensureUser(): Promise<string> {
  const existing = memoryToken ?? getToken()
  if (existing) return Promise.resolve(existing)
  return Promise.reject(new Error('Finish the first-visit screens first'))
}

/** Create the user once the age check, consent and coach are chosen (UW1). */
export async function signUp(choices: {
  consent: Record<string, boolean>
  persona: Persona
}): Promise<string> {
  let timezone: string | undefined
  try {
    timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
  } catch {
    timezone = undefined
  }
  const created = await request<{ user_id: string; token: string }>('/users', {
    method: 'POST',
    body: JSON.stringify({ age_confirmed: true, timezone, ...choices }),
  })
  memoryToken = created.token
  setToken(created.token)
  return created.token
}

/** After "Delete everything": forget this browser's user. */
export function forgetUser(): void {
  memoryToken = null
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('lodestar.session')
    localStorage.removeItem('lodestar.voice.baseline') // voice tone baseline (affect/voiceTone.ts)
  } catch {
    // nothing stored
  }
}

const OWN_TOKEN_KEY = 'lodestar.token.own'
const DEMO_KEY = 'lodestar.demo'

/** Whether this browser is looking around as the demo user. */
export function inDemo(): boolean {
  try {
    return localStorage.getItem(DEMO_KEY) === '1'
  } catch {
    return false
  }
}

/** Sign in as the demo user (Alex, four months of practice), keeping this browser's own sign-in to
 * come back to. The page reloads afterwards. */
export async function startDemo(): Promise<void> {
  type DemoReply = { user_id: string; token: string } | { status: 'preparing' }
  let demo = await request<DemoReply>('/demo', { method: 'POST' })
  for (let attempt = 0; 'status' in demo && attempt < 300; attempt++) {
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, 1500)
    })
    demo = await request<DemoReply>('/demo', { method: 'POST' })
  }
  if ('status' in demo)
    throw new Error(t('The demo is still being prepared. Please try again shortly.'))
  const own = memoryToken ?? getToken()
  try {
    if (own && !inDemo()) localStorage.setItem(OWN_TOKEN_KEY, own)
    localStorage.setItem(DEMO_KEY, '1')
    localStorage.removeItem('lodestar.session')
  } catch {
    // Private mode: the demo lasts until the page closes.
  }
  memoryToken = demo.token
  setToken(demo.token)
}

/** Back to this browser's own user, or to the first-visit screens if there isn't one. */
export function endDemo(): void {
  let own: string | null = null
  try {
    own = localStorage.getItem(OWN_TOKEN_KEY)
    for (const key of [OWN_TOKEN_KEY, DEMO_KEY, 'lodestar.session', TOKEN_KEY])
      localStorage.removeItem(key)
  } catch {
    // nothing stored
  }
  memoryToken = own
  if (own) setToken(own)
}

/** Download a response body as a file. */
async function download(path: string, filename: string): Promise<void> {
  const token = memoryToken ?? getToken()
  const response = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) throw new ApiError(response.status, response.statusText)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export interface SessionStart {
  session_id: string
  events: AgentEvent[]
}

export const api = {
  documentPages: (id: string) =>
    request<
      { page: number; text: string; warnings: string[]; translations?: Record<string, string> }[]
    >(`/documents/${id}/pages`),
  reviewDocument: (id: string, pages: string[]) =>
    request<DocumentView>(`/documents/${id}/review`, {
      method: 'PUT',
      body: JSON.stringify({ pages }),
    }),
  documentOriginal: async (id: string) => {
    const token = memoryToken ?? getToken()
    const response = await fetch(`${API_BASE}/documents/${id}/original`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) throw new ApiError(response.status, 'Original PDF is unavailable.')
    return response.blob()
  },
  subjects: () => request<SubjectView[]>('/subjects'),
  createSubject: (name: string) =>
    request<SubjectView>('/subjects', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  documents: () => request<DocumentView[]>('/documents'),
  uploadDocument: (file: File, subjectId: string, chapter: string, gemini = false) => {
    const body = new FormData()
    body.append('file', file)
    if (subjectId) body.append('subject_id', subjectId)
    body.append('chapter', chapter)
    body.append('gemini', String(gemini))
    return request<DocumentView>('/documents', { method: 'POST', body })
  },
  approveDocument: (id: string) =>
    request<DocumentView>(`/documents/${id}/approve`, { method: 'POST' }),
  deleteDocument: (id: string) => request<undefined>(`/documents/${id}`, { method: 'DELETE' }),
  searchDocuments: (query: string, docId = '') =>
    request<PassageView[]>(
      `/documents/search?q=${encodeURIComponent(query)}${docId ? `&doc_id=${encodeURIComponent(docId)}` : ''}`,
    ),
  registry: () => request<Registry>('/registry'),
  course: () => request<CourseMapView>('/course'),
  classView: () => request<ClassView>('/class'),
  twin: () => request<TwinView>('/twin'),
  startSession: (trigger: 'ui' | 'voice' = 'ui', message?: string) =>
    request<SessionStart>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ trigger, message: message ?? null }),
    }),
  label: (body: {
    session_id: string
    kind: 'mood' | 'was_i_right' | 'rushed'
    value: string
    round_id?: string
    decision_id?: string
  }) => request<undefined>('/affect/labels', { method: 'POST', body: JSON.stringify(body) }),
  cues: (body: {
    session_id: string
    strain_cue: number | null
    voice_strain_cue: number | null
  }) => request<undefined>('/affect/cues', { method: 'POST', body: JSON.stringify(body) }),
  pending: (sessionId: string) =>
    request<{ pending: AgentEvent | null }>(`/sessions/${sessionId}/pending`),
  decision: (decisionId: string) => request<Decision>(`/decisions/${decisionId}`),
  consent: () => request<ConsentView>('/consent'),
  setConsent: (switchId: string, granted: boolean) =>
    request<ConsentView>(`/consent/${switchId}`, {
      method: 'PUT',
      body: JSON.stringify({ granted }),
    }),
  llm: () => request<LlmOverview>('/llm/providers'),
  saveKey: (provider: string, apiKey: string) =>
    request<KeySaved>(`/llm/credentials/${provider}`, {
      method: 'PUT',
      body: JSON.stringify({ api_key: apiKey }),
    }),
  removeKey: (provider: string) =>
    request<undefined>(`/llm/credentials/${provider}`, { method: 'DELETE' }),
  select: (selection: LlmSelection) =>
    request<LlmSelection>('/llm/selection', {
      method: 'PUT',
      body: JSON.stringify(selection),
    }),
  myData: () => request<MyData>('/me/data'),
  forgetCoreLine: (line: string) =>
    request<undefined>('/me/core/forget', { method: 'POST', body: JSON.stringify({ line }) }),
  forgetMemory: (collection: string, id: string) =>
    request<undefined>(`/me/memories/${collection}/${id}`, { method: 'DELETE' }),
  forgetLifeContext: (id: string) =>
    request<undefined>(`/me/life-context/${id}`, { method: 'DELETE' }),
  exportData: () => download('/me/export', 'lodestar-export.json'),
  deleteEverything: () => request<Receipt>('/me', { method: 'DELETE' }),
  goals: () => request<GoalView[]>('/goals'),
  progress: () => request<ProgressView>('/progress'),
  me: () => request<MeView>('/me'),
  experiments: () => request<ExperimentView[]>('/experiments'),
  cancelExperiment: (id: string) =>
    request<undefined>(`/experiments/${id}/cancel`, { method: 'POST' }),
  forecast: (sessions = 5) => request<ForecastView[]>(`/forecast?sessions=${String(sessions)}`),
  acs: () => request<AcsView>('/acs'),
  patterns: () => request<PatternsView>('/me/patterns'),
  insights: () => request<InsightsView>('/me/insights'),
  models: () => request<ModelCard[]>('/about/models'),
  setPersona: (persona: Persona) =>
    request<undefined>('/me/persona', { method: 'PUT', body: JSON.stringify({ persona }) }),
  decisions: (limit = 20) => request<Decision[]>(`/me/decisions?limit=${String(limit)}`),
  trace: (sessionId: string) => request<TraceRow[]>(`/sessions/${sessionId}/trace`),
  sendTrials: (trials: TrialEvent[]) =>
    request<{ accepted: number; duplicates: number }>('/events', {
      method: 'POST',
      body: JSON.stringify({ trials }),
    }),
}
