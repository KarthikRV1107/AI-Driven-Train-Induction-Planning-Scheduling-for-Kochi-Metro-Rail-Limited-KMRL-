// ============================================================
// KMRL NexusAI — k6 Load Test Suite
// ============================================================
// Run:  k6 run tests/load/load_test.js
// Soak: k6 run --duration 30m tests/load/load_test.js
// Stress: k6 run --vus 200 --duration 5m tests/load/load_test.js

import http from 'k6/http'
import { check, group, sleep } from 'k6'
import { Counter, Rate, Trend } from 'k6/metrics'
import { SharedArray } from 'k6/data'

// ── Custom Metrics ────────────────────────────────────────────────────────

const optimizerDuration   = new Trend('kmrl_optimizer_duration_ms')
const mlPredictionLatency = new Trend('kmrl_ml_prediction_ms')
const wsMessageLatency    = new Trend('kmrl_ws_message_ms')
const errorRate           = new Rate('kmrl_error_rate')
const alertsAcked         = new Counter('kmrl_alerts_acknowledged')

// ── Config ────────────────────────────────────────────────────────────────

const BASE_URL  = __ENV.BASE_URL  || 'http://localhost:8000'
const WS_URL    = __ENV.WS_URL    || 'ws://localhost:8000'
const API_TOKEN = __ENV.API_TOKEN || ''

// ── Test Scenarios ────────────────────────────────────────────────────────

export const options = {
  scenarios: {
    // Scenario 1: Steady-state — normal operational load
    steady_state: {
      executor:         'constant-vus',
      vus:              20,
      duration:         '5m',
      gracefulStop:     '30s',
      tags:             { scenario: 'steady_state' },
    },

    // Scenario 2: Planning window surge — 21:00 evening rush
    planning_window_spike: {
      executor:         'ramping-vus',
      startVUs:         5,
      stages: [
        { duration: '1m', target: 50  },   // ramp up (planning window opens)
        { duration: '3m', target: 50  },   // hold — all operators checking plan
        { duration: '1m', target: 5   },   // ramp down
      ],
      startTime:        '5m',
      gracefulStop:     '30s',
      tags:             { scenario: 'planning_spike' },
    },

    // Scenario 3: Optimizer stress — multiple simultaneous solves
    optimizer_stress: {
      executor:         'ramping-arrival-rate',
      startRate:        1,
      timeUnit:         '30s',
      preAllocatedVUs:  10,
      maxVUs:           30,
      stages: [
        { duration: '2m', target: 4  },    // 4 optimizer calls/30s
        { duration: '3m', target: 8  },
        { duration: '2m', target: 2  },
      ],
      startTime:        '10m',
      tags:             { scenario: 'optimizer_stress' },
      exec:             'optimizerOnly',
    },

    // Scenario 4: WebSocket sustained connections
    websocket_connections: {
      executor:         'constant-vus',
      vus:              50,
      duration:         '3m',
      startTime:        '7m',
      exec:             'wsOnly',
      tags:             { scenario: 'websocket' },
    },
  },

  thresholds: {
    // API performance SLAs
    'http_req_duration{scenario:steady_state}': [
      'p(95)<500',   // 95th percentile < 500ms
      'p(99)<2000',  // 99th percentile < 2s
    ],
    'http_req_duration{scenario:planning_spike}': [
      'p(95)<800',
    ],
    // Optimizer must complete within 35s (30s solve + overhead)
    'kmrl_optimizer_duration_ms': ['p(95)<35000'],
    // ML inference < 200ms
    'kmrl_ml_prediction_ms':      ['p(95)<200'],
    // Error rate < 1%
    'kmrl_error_rate':            ['rate<0.01'],
    // HTTP failure rate < 0.5%
    'http_req_failed':            ['rate<0.005'],
  },
}

// ── Helpers ───────────────────────────────────────────────────────────────

function authHeaders() {
  return {
    'Authorization': `Bearer ${API_TOKEN}`,
    'Content-Type':  'application/json',
  }
}

function getToken() {
  const res = http.post(
    `${BASE_URL}/api/v1/auth/token`,
    'username=depot_controller%40kmrl.in&password=kmrl%402025',
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  )
  if (res.status === 200) {
    return res.json('access_token')
  }
  return ''
}

// ── Default Scenario — Mixed Operations ───────────────────────────────────

export default function () {
  const token   = getToken()
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }

  group('Health Check', () => {
    const res = http.get(`${BASE_URL}/health`)
    check(res, {
      'health status 200':   r => r.status === 200,
      'health returns ok':   r => r.json('status') !== 'error',
    })
  })

  sleep(0.5)

  group('KPI Dashboard', () => {
    const start = Date.now()
    const res   = http.get(`${BASE_URL}/api/v1/kpis`, { headers })
    check(res, {
      'kpis status 200':              r => r.status === 200,
      'kpis has availability_pct':    r => r.json('fleet_availability_pct') !== undefined,
      'kpis has revenue_count':       r => r.json('revenue_service_count') !== undefined,
    })
    errorRate.add(res.status >= 400)
  })

  sleep(1)

  group('Fleet List', () => {
    const res = http.get(`${BASE_URL}/api/v1/fleet`, { headers })
    check(res, {
      'fleet status 200':         r => r.status === 200,
      'fleet returns trainsets':  r => Array.isArray(r.json('trainsets')),
      'fleet count >= 20':        r => (r.json('trainsets') || []).length >= 20,
    })
    errorRate.add(res.status >= 400)
  })

  sleep(0.5)

  group('Maintenance Predictions', () => {
    const start = Date.now()
    const res   = http.get(`${BASE_URL}/api/v1/maintenance/predictions`, { headers })
    const dur   = Date.now() - start
    mlPredictionLatency.add(dur)
    check(res, {
      'ml predictions 200':        r => r.status === 200,
      'ml predictions non-empty':  r => (r.json('predictions') || []).length > 0,
      'ml latency < 1s':           () => dur < 1000,
    })
    errorRate.add(res.status >= 400)
  })

  sleep(1)

  group('Alerts', () => {
    const res = http.get(`${BASE_URL}/api/v1/alerts?limit=20`, { headers })
    check(res, {
      'alerts status 200':   r => r.status === 200,
      'alerts has total':    r => r.json('total') !== undefined,
    })
    errorRate.add(res.status >= 400)
  })

  sleep(1)

  group('Analytics Trend', () => {
    const res = http.get(`${BASE_URL}/api/v1/analytics/availability-trend?days=30`, { headers })
    check(res, {
      'trend status 200':  r => r.status === 200,
      'trend has data':    r => Array.isArray(r.json('trend')),
    })
  })

  sleep(2)
}

// ── Optimizer-Only Scenario ────────────────────────────────────────────────

export function optimizerOnly() {
  const token   = getToken()
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }

  const body = JSON.stringify({
    depot_id:   'dep-001',
    plan_date:  new Date().toISOString().split('T')[0],
  })

  const start = Date.now()
  const res   = http.post(`${BASE_URL}/api/v1/induction/optimize`, body, { headers, timeout: '40s' })
  const dur   = Date.now() - start

  optimizerDuration.add(dur)
  check(res, {
    'optimizer 200':           r => r.status === 200,
    'optimizer has score':     r => r.json('score') !== undefined,
    'optimizer score > 0':     r => (r.json('score') || 0) > 0,
    'revenue service present': r => Array.isArray(r.json('revenue_service')),
    'revenue count >= 15':     r => (r.json('revenue_service') || []).length >= 15,
    'solve time < 30s':        r => (r.json('solve_time_ms') || 99999) < 30000,
    'status is feasible':      r => ['optimal', 'feasible'].includes(r.json('status')),
  })
  errorRate.add(res.status >= 400)

  sleep(5)  // Optimizer is expensive — space calls out
}

// ── WebSocket Scenario ────────────────────────────────────────────────────

export function wsOnly() {
  // k6 WebSocket test
  const ws = http.get(`${BASE_URL}/health`)  // k6 ws module would be used in real run
  // Note: use k6/ws in production k6 scripts:
  // import ws from 'k6/ws'
  // const res = ws.connect(`${WS_URL}/ws/live?token=${token}`, {}, (socket) => {
  //   socket.on('open', () => { socket.send(JSON.stringify({ type: 'ping' })) })
  //   socket.on('message', (data) => { wsMessageLatency.add(Date.now() - start) })
  //   socket.setTimeout(() => socket.close(), 30000)
  // })
  sleep(30)
}

// ── Soak Test (long-running stability) ────────────────────────────────────

export function soakTest() {
  // Run as: k6 run --env SOAK=true --duration 4h tests/load/load_test.js
  const token   = getToken()
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }

  http.get(`${BASE_URL}/api/v1/kpis`, { headers })
  http.get(`${BASE_URL}/api/v1/fleet`, { headers })
  http.get(`${BASE_URL}/api/v1/alerts`, { headers })
  sleep(10)
}
