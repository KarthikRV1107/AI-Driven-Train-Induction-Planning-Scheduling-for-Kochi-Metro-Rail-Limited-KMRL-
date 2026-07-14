// ============================================================
// KMRL NexusAI — TypeScript Types & API Client
// ============================================================

// ── Core Types ────────────────────────────────────────────────────────────

export type TrainsetStatus =
  | 'revenue_service' | 'standby' | 'ibl'
  | 'maintenance' | 'cleaning' | 'stabling' | 'out_of_service'

export type AlertSeverity = 'critical' | 'warning' | 'info'
export type UserRole =
  | 'admin' | 'depot_controller' | 'maintenance_supervisor'
  | 'operations_manager' | 'cleaning_team_lead' | 'branding_manager'

export interface Trainset {
  id: string
  trainset_code: string
  rake_number: string
  current_status: TrainsetStatus
  current_bay: string | null
  total_mileage_km: number
  brake_health: number
  hvac_health: number
  door_health: number
  days_since_service: number
  days_since_ibl: number
  open_jobs: number
  critical_jobs: number
  is_active: boolean
  last_updated: string
  metadata?: Record<string, unknown>
}

export interface FitnessCertificate {
  id: string
  trainset_id: string
  cert_type: string
  cert_number: string | null
  issuing_authority: string | null
  issued_date: string
  expiry_date: string
  status: 'valid' | 'expiring_soon' | 'expired' | 'pending_renewal'
  days_to_expiry: number
}

export interface MaintenanceJob {
  id: string
  trainset_code: string
  job_type: string
  system_affected: string
  description: string | null
  priority: 'critical' | 'high' | 'medium' | 'low'
  status: 'open' | 'in_progress' | 'completed' | 'deferred'
  estimated_hours: number | null
  ibm_maximo_ref: string | null
  is_critical: boolean
}

export interface PlanItem {
  rank: number
  trainset_code: string
  confidence_pct: number
  reasoning: {
    soft_score: number
    human_reasons: string[]
    hard_violations: string[]
    factors?: Record<string, number>
  }
  constraint_violations: string[]
}

export interface InductionPlan {
  plan_id: string
  plan_date: string
  status: 'optimal' | 'feasible' | 'fallback'
  score: number
  solve_time_ms: number
  optimizer_version: string
  revenue_service: PlanItem[]
  standby: Array<{ trainset_code: string; confidence_pct: number }>
  ibl: Array<{ trainset_code: string; constraint_violations: string[] }>
  maintenance: Array<{ trainset_code: string; constraint_violations: string[] }>
  total_shunting_ops: number
  mileage_variance_km: number
  sla_compliance_pct: number
  conflict_alerts: Array<{ trainset: string; violations: string[]; severity: string }>
  explanation: string
  created_at: string
}

export interface KPIs {
  fleet_availability_pct: number
  revenue_service_count: number
  standby_count: number
  ibl_count: number
  maintenance_count: number
  total_shunting_ops_today: number
  avg_mileage_km: number
  mileage_std_km: number
  active_alerts_critical: number
  active_alerts_warning: number
  sla_compliance_pct: number
  mtbf_days: number
  mttr_hours: number
  ai_confidence_avg: number
}

export interface Alert {
  id: string
  alert_code: string
  severity: AlertSeverity
  trainset_code: string | null
  title: string
  description: string | null
  is_acknowledged: boolean
  created_at: string
}

export interface MaintenancePrediction {
  trainset_code: string
  risk_profile: {
    composite_failure_risk: number
    risk_level: 'low' | 'medium' | 'high' | 'critical'
    recommendation: string
    systems: Record<string, {
      failure_probability: number
      risk_level: string
      top_shap_features?: Record<string, number>
    }>
  }
  assessed_at: string
}

export interface DepotBay {
  bay_code: string
  bay_type: 'stabling' | 'ibl' | 'cleaning' | 'maintenance'
  is_occupied: boolean
  trainset_code: string | null
}

export interface SimulationResult {
  scenario_name: string
  baseline_shunting_ops: number
  optimized_shunting_ops: number
  reduction_pct: number
  total_time_mins: number
  conflicts_detected: number
  conflicts_resolved: number
  fleet_readiness_pct: number
  timeline: Array<Record<string, unknown>>
  shunt_moves: Array<Record<string, unknown>>
  alerts: string[]
  kpis: Record<string, unknown>
}

export interface User {
  user_id: string
  role: UserRole
  depot_id?: string
}

export interface CopilotChatResponse {
  response: string
  timestamp: string
}

// ── API Client ────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const WS_BASE  = process.env.NEXT_PUBLIC_WS_URL  ?? 'ws://localhost:8000'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== 'undefined'
    ? localStorage.getItem('kmrl_token')
    : null

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new ApiError(res.status, err.error ?? res.statusText)
  }

  return res.json() as Promise<T>
}

// ── Auth ──────────────────────────────────────────────────────────────────

export const authApi = {
  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password })
    const res = await fetch(`${API_BASE}/api/v1/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })
    if (!res.ok) throw new ApiError(res.status, 'Invalid credentials')
    const data = await res.json()
    if (typeof window !== 'undefined') {
      localStorage.setItem('kmrl_token', data.access_token)
      localStorage.setItem('kmrl_user', JSON.stringify({ user_id: data.user_id, role: data.role }))
    }
    return data
  },
  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('kmrl_token')
      localStorage.removeItem('kmrl_user')
    }
  },
  getUser: (): User | null => {
    if (typeof window === 'undefined') return null
    try {
      return JSON.parse(localStorage.getItem('kmrl_user') ?? 'null')
    } catch { return null }
  },
}

// ── Fleet ─────────────────────────────────────────────────────────────────

export const fleetApi = {
  list: (statusFilter?: string) =>
    fetchJson<{ trainsets: Trainset[]; total: number }>(
      `/api/v1/fleet${statusFilter ? `?status_filter=${statusFilter}` : ''}`
    ),
  get: (code: string) =>
    fetchJson<Trainset>(`/api/v1/fleet/${code}`),
  updateStatus: (code: string, status: TrainsetStatus, reason?: string) =>
    fetchJson<{ updated: boolean }>(`/api/v1/fleet/${code}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, reason }),
    }),
}

// ── Induction ─────────────────────────────────────────────────────────────

export const inductionApi = {
  optimize: (depotId: string, planDate?: string, revenueTarget?: number) =>
    fetchJson<InductionPlan>('/api/v1/induction/optimize', {
      method: 'POST',
      body: JSON.stringify({
        depot_id: depotId,
        plan_date: planDate ?? new Date().toISOString().split('T')[0],
        override_revenue_target: revenueTarget,
      }),
    }),
  getPlan: (date: string) =>
    fetchJson<{ data: InductionPlan }>(`/api/v1/induction/plans/${date}`),
  listPlans: () =>
    fetchJson<{ plans: InductionPlan[] }>('/api/v1/induction/plans'),
  exportPDF: async (planDate: string) => {
    const token = localStorage.getItem('kmrl_token') ?? ''
    const res = await fetch(`${API_BASE}/api/v1/induction/plans/${planDate}/export`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) throw new ApiError(res.status, 'Export failed')
    return res.blob()
  },
}

// ── KPIs ──────────────────────────────────────────────────────────────────

export const analyticsApi = {
  kpis: () => fetchJson<KPIs>('/api/v1/kpis'),
  mileage: (days = 30) =>
    fetchJson<{ per_trainset: Array<{ code: string; mileage_km: number }> }>(
      `/api/v1/analytics/mileage?days=${days}`
    ),
  availabilityTrend: (days = 30) =>
    fetchJson<{ trend: Array<{ date: string; availability_pct: number }> }>(
      `/api/v1/analytics/availability-trend?days=${days}`
    ),
}

// ── Maintenance ───────────────────────────────────────────────────────────

export const maintenanceApi = {
  predictions: () =>
    fetchJson<{ predictions: MaintenancePrediction[] }>('/api/v1/maintenance/predictions'),
  jobs: (status?: string) =>
    fetchJson<{ jobs: MaintenanceJob[] }>(
      `/api/v1/maintenance/jobs${status ? `?status=${status}` : ''}`
    ),
  createJob: (data: Partial<MaintenanceJob>) =>
    fetchJson<MaintenanceJob>('/api/v1/maintenance/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// ── Alerts ────────────────────────────────────────────────────────────────

export const alertsApi = {
  list: (severity?: AlertSeverity, acknowledged?: boolean) => {
    const params = new URLSearchParams()
    if (severity) params.set('severity', severity)
    if (acknowledged !== undefined) params.set('acknowledged', String(acknowledged))
    return fetchJson<{ alerts: Alert[]; total: number }>(`/api/v1/alerts?${params}`)
  },
  acknowledge: (id: string) =>
    fetchJson<{ acknowledged: boolean }>(`/api/v1/alerts/${id}/acknowledge`, { method: 'PATCH' }),
}

// ── Certificates ──────────────────────────────────────────────────────────

export const certsApi = {
  list: (expiringWithinDays?: number) =>
    fetchJson<{ certificates: FitnessCertificate[] }>(
      `/api/v1/certificates${expiringWithinDays ? `?expiring_within_days=${expiringWithinDays}` : ''}`
    ),
}

export const copilotApi = {
  chat: (message: string) =>
    fetchJson<CopilotChatResponse>('/api/v1/copilot/chat', {
      method: 'POST',
      body: JSON.stringify({ message, stream: false }),
    }),
}

// ── Depot ─────────────────────────────────────────────────────────────────

export const depotApi = {
  layout: (depotCode = 'MTM') =>
    fetchJson<{ bays: DepotBay[]; occupied_bays: number; total_bays: number }>(
      `/api/v1/depot/${depotCode}/layout`
    ),
  simulate: (scenario: string, params?: Record<string, unknown>) =>
    fetchJson<SimulationResult>('/api/v1/depot/simulate', {
      method: 'POST',
      body: JSON.stringify({ depot_id: 'dep-001', scenario, parameters: params }),
    }),
}

// ── WebSocket ─────────────────────────────────────────────────────────────

export type WSEvent =
  | { event: 'connected'; message: string; timestamp: string }
  | { event: 'trainset_status_update'; trainset_code: string; new_status: TrainsetStatus; timestamp: string }
  | { event: 'induction_plan_ready'; plan_date: string; score: number; revenue_count: number; timestamp: string }
  | { event: 'alert_raised'; alert: Alert; timestamp: string }
  | { type: 'pong'; timestamp: string }

export function createWebSocket(onMessage: (evt: WSEvent) => void): WebSocket {
  const token = typeof window !== 'undefined' ? localStorage.getItem('kmrl_token') ?? '' : ''
  const ws = new WebSocket(`${WS_BASE}/ws/live?token=${token}`)

  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data) as WSEvent) }
    catch { /* ignore malformed */ }
  }

  ws.onerror = (e) => console.error('[KMRL WS] error', e)

  // Keepalive
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, 30_000)

  ws.onclose = () => clearInterval(pingInterval)
  return ws
}
