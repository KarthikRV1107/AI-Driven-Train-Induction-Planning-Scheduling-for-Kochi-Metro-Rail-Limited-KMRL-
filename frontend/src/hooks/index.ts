// ============================================================
// KMRL NexusAI — Custom React Hooks
// ============================================================
'use client'

import {
  useCallback, useEffect, useReducer, useRef, useState,
} from 'react'
import {
  Alert, AlertSeverity, InductionPlan, KPIs,
  MaintenancePrediction, Trainset, WSEvent,
  alertsApi, analyticsApi, createWebSocket, fleetApi,
  inductionApi, maintenanceApi,
} from '@/lib/api'

// ── Generic Async Hook ────────────────────────────────────────────────────

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

type AsyncAction<T> =
  | { type: 'loading' }
  | { type: 'success'; payload: T }
  | { type: 'error'; payload: string }

function asyncReducer<T>(state: AsyncState<T>, action: AsyncAction<T>): AsyncState<T> {
  switch (action.type) {
    case 'loading': return { ...state, loading: true, error: null }
    case 'success': return { data: action.payload, loading: false, error: null }
    case 'error':   return { ...state, loading: false, error: action.payload }
  }
}

function useAsync<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): AsyncState<T> & { refetch: () => void } {
  const [state, dispatch] = useReducer(asyncReducer<T>, {
    data: null, loading: true, error: null,
  })

  const fetch = useCallback(async () => {
    dispatch({ type: 'loading' })
    try {
      const data = await fetcher()
      dispatch({ type: 'success', payload: data })
    } catch (err) {
      dispatch({ type: 'error', payload: err instanceof Error ? err.message : 'Unknown error' })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => { fetch() }, [fetch])

  return { ...state, refetch: fetch }
}

// ── Fleet Hook ────────────────────────────────────────────────────────────

export function useFleet(statusFilter?: string) {
  return useAsync(
    () => fleetApi.list(statusFilter).then(r => r.trainsets),
    [statusFilter],
  )
}

export function useTrainset(code: string) {
  return useAsync(() => fleetApi.get(code), [code])
}

// ── KPIs Hook (auto-refresh every 30s) ───────────────────────────────────

export function useKPIs(refreshInterval = 30_000) {
  const state = useAsync(() => analyticsApi.kpis(), [])
  const { refetch } = state

  useEffect(() => {
    const id = setInterval(refetch, refreshInterval)
    return () => clearInterval(id)
  }, [refetch, refreshInterval])

  return state
}

// ── Analytics Hook ────────────────────────────────────────────────────────

export function useAvailabilityTrend(days = 30) {
  return useAsync(
    () => analyticsApi.availabilityTrend(days).then(r => r.trend),
    [days],
  )
}

export function useMileageData(days = 30) {
  return useAsync(
    () => analyticsApi.mileage(days).then(r => r.per_trainset),
    [days],
  )
}

// ── Induction Hook ────────────────────────────────────────────────────────

interface UseOptimizerReturn {
  plan: InductionPlan | null
  running: boolean
  error: string | null
  runOptimizer: (depotId?: string, revenueTarget?: number) => Promise<void>
  clearPlan: () => void
}

export function useOptimizer(): UseOptimizerReturn {
  const [plan, setPlan] = useState<InductionPlan | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runOptimizer = useCallback(async (
    depotId = 'dep-001',
    revenueTarget?: number,
  ) => {
    setRunning(true)
    setError(null)
    try {
      const result = await inductionApi.optimize(depotId, undefined, revenueTarget)
      setPlan(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Optimization failed')
    } finally {
      setRunning(false)
    }
  }, [])

  return { plan, running, error, runOptimizer, clearPlan: () => setPlan(null) }
}

// ── Maintenance Predictions Hook ──────────────────────────────────────────

export function useMaintenancePredictions() {
  return useAsync<MaintenancePrediction[]>(
    () => maintenanceApi.predictions().then(r => r.predictions),
    [],
  )
}

// ── Alerts Hook ───────────────────────────────────────────────────────────

interface UseAlertsReturn {
  alerts: Alert[]
  loading: boolean
  error: string | null
  criticalCount: number
  warningCount: number
  acknowledge: (id: string) => Promise<void>
  refetch: () => void
}

export function useAlerts(
  severity?: AlertSeverity,
  acknowledged?: boolean,
): UseAlertsReturn {
  const state = useAsync(
    () => alertsApi.list(severity, acknowledged).then(r => r.alerts),
    [severity, acknowledged],
  )

  const acknowledge = useCallback(async (id: string) => {
    await alertsApi.acknowledge(id)
    state.refetch()
  }, [state])

  const criticalCount = state.data?.filter(a => a.severity === 'critical' && !a.is_acknowledged).length ?? 0
  const warningCount  = state.data?.filter(a => a.severity === 'warning'  && !a.is_acknowledged).length ?? 0

  return {
    alerts: state.data ?? [],
    loading: state.loading,
    error: state.error,
    criticalCount,
    warningCount,
    acknowledge,
    refetch: state.refetch,
  }
}

// ── WebSocket Hook ────────────────────────────────────────────────────────

interface UseWebSocketReturn {
  connected: boolean
  lastEvent: WSEvent | null
  latestStatusUpdates: Record<string, string>  // trainset_code → status
  latestPlanScore: number | null
}

export function useWebSocket(): UseWebSocketReturn {
  const [connected, setConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null)
  const [latestStatusUpdates, setLatestStatusUpdates] = useState<Record<string, string>>({})
  const [latestPlanScore, setLatestPlanScore] = useState<number | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let reconnectTimeout: ReturnType<typeof setTimeout>

    const connect = () => {
      const ws = createWebSocket((event) => {
        setLastEvent(event)
        if ('event' in event) {
          if (event.event === 'connected') setConnected(true)
          if (event.event === 'trainset_status_update') {
            setLatestStatusUpdates(prev => ({
              ...prev,
              [event.trainset_code]: event.new_status,
            }))
          }
          if (event.event === 'induction_plan_ready') {
            setLatestPlanScore(event.score)
          }
        }
      })

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        reconnectTimeout = setTimeout(connect, 5_000)
      }
      wsRef.current = ws
    }

    connect()
    return () => {
      clearTimeout(reconnectTimeout)
      wsRef.current?.close()
    }
  }, [])

  return { connected, lastEvent, latestStatusUpdates, latestPlanScore }
}

// ── Clock Hook ────────────────────────────────────────────────────────────

export function useISTClock(): string {
  const [time, setTime] = useState('')

  useEffect(() => {
    const update = () => {
      setTime(new Date().toLocaleTimeString('en-IN', {
        hour12: false,
        timeZone: 'Asia/Kolkata',
      }))
    }
    update()
    const id = setInterval(update, 1_000)
    return () => clearInterval(id)
  }, [])

  return time
}

// ── Depot Layout Hook ─────────────────────────────────────────────────────

export function useDepotLayout(depotCode = 'MTM') {
  return useAsync(
    () => import('@/lib/api').then(m => m.depotApi.layout(depotCode)),
    [depotCode],
  )
}

// ── Simulation Hook ───────────────────────────────────────────────────────

interface UseSimulationReturn {
  result: import('@/lib/api').SimulationResult | null
  running: boolean
  error: string | null
  runScenario: (scenario: string, params?: Record<string, unknown>) => Promise<void>
}

export function useSimulation(): UseSimulationReturn {
  const [result, setResult] = useState<import('@/lib/api').SimulationResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runScenario = useCallback(async (
    scenario: string,
    params?: Record<string, unknown>,
  ) => {
    setRunning(true)
    setError(null)
    try {
      const r = await import('@/lib/api').then(m => m.depotApi.simulate(scenario, params))
      setResult(r)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed')
    } finally {
      setRunning(false)
    }
  }, [])

  return { result, running, error, runScenario }
}

// ── Local Storage Hook ────────────────────────────────────────────────────

export function useLocalStorage<T>(key: string, initial: T): [T, (val: T) => void] {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initial
    try {
      const stored = localStorage.getItem(key)
      return stored !== null ? (JSON.parse(stored) as T) : initial
    } catch { return initial }
  })

  const set = useCallback((val: T) => {
    setValue(val)
    try { localStorage.setItem(key, JSON.stringify(val)) } catch { /* ignore */ }
  }, [key])

  return [value, set]
}

// ── Keyboard Shortcut Hook ────────────────────────────────────────────────

export function useKeyboardShortcut(
  key: string,
  handler: () => void,
  modifiers: ('ctrl' | 'meta' | 'shift')[] = ['meta'],
) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const modOk = modifiers.every(mod => {
        if (mod === 'meta')  return e.metaKey || e.ctrlKey
        if (mod === 'ctrl')  return e.ctrlKey
        if (mod === 'shift') return e.shiftKey
        return false
      })
      if (modOk && e.key.toLowerCase() === key.toLowerCase()) {
        e.preventDefault()
        handler()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [key, handler, modifiers])
}
