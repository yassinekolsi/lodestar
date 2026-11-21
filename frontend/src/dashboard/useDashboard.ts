import { useCallback, useEffect, useRef, useState } from 'react'

import { API_BASE, ApiError, api, getToken, withLang } from '../api/client'
import type {
  AcsView,
  CourseMapView,
  Decision,
  ForecastView,
  GoalView,
  PatternsView,
  ProgressView,
  Registry,
  TwinView,
} from '../api/types'

export interface DashboardData {
  registry: Registry | null
  twin: TwinView | null
  progress: ProgressView | null
  forecast: ForecastView[]
  goals: GoalView[]
  acs: AcsView | null
  decisions: Decision[]
  patterns: PatternsView | null
  course: CourseMapView | null
  /** No built-in course for this account: it studies its own uploads (backend/course_scope.py). */
  ownMaterial: boolean
  error: string | null
  /** Bumped on every live "twin updated" push, so views can animate a change. */
  updates: number
}

const EMPTY: DashboardData = {
  registry: null,
  twin: null,
  progress: null,
  forecast: [],
  goals: [],
  acs: null,
  decisions: [],
  patterns: null,
  course: null,
  ownMaterial: false,
  error: null,
  updates: 0,
}

/** Everything the dashboard shows, refreshed whenever the profile changes anywhere
 * (`/twin/stream`, fed by the scored-round transaction's NOTIFY). */
export function useDashboard(enabled: boolean): DashboardData & { refresh: () => void } {
  const [data, setData] = useState<DashboardData>(EMPTY)
  const socket = useRef<WebSocket | null>(null)

  const refresh = useCallback(() => {
    Promise.all([
      api.registry(),
      api.twin(),
      api.progress(),
      api.forecast(),
      api.goals(),
      api.acs(),
      api.decisions(),
      api.patterns(),
      api.course().then(
        (course) => ({ course, ownMaterial: false }),
        (e: unknown) => ({ course: null, ownMaterial: e instanceof ApiError && e.status === 404 }),
      ),
    ]).then(
      ([registry, twin, progress, forecast, goals, acs, decisions, patterns, map]) => {
        setData((d) => ({
          ...d,
          registry,
          twin,
          progress,
          forecast,
          goals,
          acs,
          decisions,
          patterns,
          course: map.course,
          ownMaterial: map.ownMaterial,
          error: null,
        }))
      },
      (e: unknown) => {
        setData((d) => ({ ...d, error: e instanceof Error ? e.message : String(e) }))
      },
    )
  }, [])

  useEffect(() => {
    if (!enabled) return
    refresh()
    const token = getToken()
    if (!token) return
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(withLang(`${scheme}://${window.location.host}${API_BASE}/twin/stream`))
    socket.current = ws
    ws.addEventListener('open', () => {
      ws.send(JSON.stringify({ type: 'auth', token }))
    })
    ws.addEventListener('message', (m: MessageEvent<string>) => {
      const event = JSON.parse(m.data) as { kind: string }
      if (event.kind === 'twin_updated') {
        setData((d) => ({ ...d, updates: d.updates + 1 }))
        refresh()
      }
    })
    return () => {
      ws.close()
      socket.current = null
    }
  }, [enabled, refresh])

  return { ...data, refresh }
}
