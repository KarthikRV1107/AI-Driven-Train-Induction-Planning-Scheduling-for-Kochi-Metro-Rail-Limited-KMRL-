'use client'

import React, { useMemo, useState } from 'react'
import AIRecommendationCard from '@/components/ai/AIRecommendationCard'
import TrainsetCard from '@/components/fleet/TrainsetCard'
import {
  Card,
  EmptyState,
  KPITile,
  LivePulse,
  SectionHeader,
  SeverityBadge,
  Skeleton,
  SkeletonCard,
} from '@/components/ui'
import { useAlerts, useFleet, useISTClock, useKPIs, useOptimizer, useWebSocket } from '@/hooks'
import { copilotApi, InductionPlan } from '@/lib/api'

function AvailabilityTrendChart({ data }: { data: number[] }) {
  const max = Math.max(...data, 100)
  const min = Math.min(...data, 80)
  const h = 60
  const w = 300
  const pts = data.map((v, i) => ({
    x: (i / (data.length - 1)) * w,
    y: h - ((v - min) / (max - min + 2)) * h,
  }))
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const area = `${path} L${w},${h} L0,${h} Z`

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 60 }}>
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity=".2" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#areaGrad)" />
        <path d={path} fill="none" stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        {pts.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={i === pts.length - 1 ? 3 : 2} fill="#3b82f6" opacity={i === pts.length - 1 ? 1 : 0.5} />
        ))}
      </svg>
    </div>
  )
}

function FleetAllocationChart({
  revenue,
  standby,
  ibl,
  maintenance,
  total,
}: {
  revenue: number
  standby: number
  ibl: number
  maintenance: number
  total: number
}) {
  const segments = [
    { value: revenue, color: '#10b981', label: 'Revenue' },
    { value: standby, color: '#f59e0b', label: 'Standby' },
    { value: ibl, color: '#8b5cf6', label: 'IBL' },
    { value: maintenance, color: '#ef4444', label: 'Maint.' },
  ]
  const cx = 60
  const cy = 60
  const r = 48
  const strokeWidth = 12
  const circumference = 2 * Math.PI * r
  let offset = 0

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
      <svg viewBox="0 0 120 120" style={{ width: 110, height: 110, flexShrink: 0 }}>
        {segments.map((seg, i) => {
          const pct = seg.value / Math.max(total, 1)
          const dash = pct * circumference
          const gap = circumference - dash
          const strokeOffset = circumference - offset
          offset += dash
          return (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={seg.color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${dash} ${gap}`}
              strokeDashoffset={strokeOffset}
              style={{ transform: 'rotate(-90deg)', transformOrigin: '60px 60px', transition: 'stroke-dashoffset .5s ease' }}
            />
          )
        })}
        <text x={cx} y={cy - 4} textAnchor="middle" fill="var(--text-0)" fontSize="18" fontWeight="700" fontFamily="var(--font-mono)">
          {total}
        </text>
        <text x={cx} y={cy + 11} textAnchor="middle" fill="var(--text-2)" fontSize="8" fontFamily="var(--font-sans)">
          TRAINS
        </text>
      </svg>
      <div style={{ display: 'grid', gap: 6, flex: 1 }}>
        {segments.map(s => (
          <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color, flexShrink: 0 }} />
            <span style={{ fontSize: 11, color: 'var(--text-1)' }}>{s.label}</span>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-0)', fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function AIInsightTicker({
  plan,
  latestPlanScore,
}: {
  plan: InductionPlan | null
  latestPlanScore: number | null
}) {
  const message = plan
    ? `Recommended ${plan.revenue_service.length} trainsets for revenue service. Score ${plan.score.toFixed(1)}/100. ${plan.conflict_alerts.length} conflicts resolved. Mileage variance sigma=${plan.mileage_variance_km.toFixed(1)}km.`
    : latestPlanScore
      ? `Latest live optimizer score received over websocket: ${latestPlanScore.toFixed(1)}.`
      : 'Run the optimizer to generate tonight\'s AI-ranked induction plan and live operational recommendations.'

  return (
    <div className="ai-ticker" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          color: 'var(--blue)',
          background: 'rgba(59,130,246,.1)',
          padding: '2px 7px',
          borderRadius: 3,
          letterSpacing: '.5px',
          flexShrink: 0,
        }}
      >
        AI INSIGHT
      </span>
      <span style={{ fontSize: 11, color: 'var(--text-1)' }}>{message}</span>
      {plan && (
        <span style={{ marginLeft: 'auto', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-2)', flexShrink: 0 }}>
          {plan.solve_time_ms.toFixed(0)}ms
        </span>
      )}
    </div>
  )
}

function WeatherOverlayCard() {
  const overlays = [
    { label: 'Rain corridor', value: 'Light rain near Maharajas', accent: '#3b82f6' },
    { label: 'Visibility', value: 'Nominal depot operations', accent: '#10b981' },
    { label: 'Peak crowding', value: 'Kaloor after 18:30 IST', accent: '#f59e0b' },
  ]

  return (
    <Card title="Weather & Operating Overlay">
      <div style={{ position: 'relative', overflow: 'hidden', borderRadius: 10, padding: 14, background: 'radial-gradient(circle at top right, rgba(59,130,246,.16), transparent 35%), linear-gradient(180deg, rgba(13,18,25,.95), rgba(8,12,16,.98))', border: '1px solid rgba(59,130,246,.12)' }}>
        <div style={{ display: 'grid', gap: 10 }}>
          {overlays.map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: item.accent, boxShadow: `0 0 0 4px ${item.accent}22` }} />
              <div>
                <div style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px' }}>{item.label}</div>
                <div style={{ fontSize: 11, color: 'var(--text-0)', marginTop: 3 }}>{item.value}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function ServiceReadinessCard({
  readiness,
  occupiedBays,
  totalBays,
}: {
  readiness: number
  occupiedBays: number
  totalBays: number
}) {
  const circumference = 226.2

  return (
    <Card title="Service Readiness">
      <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: 14, alignItems: 'center' }}>
        <div style={{ position: 'relative', width: 96, height: 96, margin: '0 auto' }}>
          <svg width="96" height="96" viewBox="0 0 96 96">
            <circle cx="48" cy="48" r="36" fill="none" stroke="var(--bg-3)" strokeWidth="10" />
            <circle
              cx="48"
              cy="48"
              r="36"
              fill="none"
              stroke="#10b981"
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference - (Math.min(readiness, 100) / 100) * circumference}
              style={{ transform: 'rotate(-90deg)', transformOrigin: '48px 48px' }}
            />
          </svg>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#10b981' }}>{readiness}%</div>
            <div style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px' }}>Ready</div>
          </div>
        </div>
        <div style={{ display: 'grid', gap: 8 }}>
          {[
            ['Depot occupancy', `${occupiedBays}/${totalBays} bays engaged`],
            ['Cleaning turnaround', '3 trainsets queued, avg recovery 18 min'],
            ['Readiness bias', '2 standby sets can absorb a rain-delay scenario'],
          ].map(([label, value]) => (
            <div key={label} style={{ padding: '9px 10px', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8 }}>
              <div style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px' }}>{label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-0)', marginTop: 4 }}>{value}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function MetroOperationsMap() {
  const stations = [
    { name: 'Aluva', x: 24, y: 116 },
    { name: 'Muttom Depot', x: 120, y: 76 },
    { name: 'Kaloor', x: 208, y: 62 },
    { name: 'Maharajas', x: 292, y: 76 },
    { name: 'Petta', x: 372, y: 120 },
  ]

  return (
    <Card title="Animated Metro Line Map" headerRight={<span style={{ fontSize: 10, color: 'var(--text-2)' }}>Live route overlay</span>}>
      <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid rgba(59,130,246,.1)', background: 'radial-gradient(circle at top left, rgba(59,130,246,.14), transparent 40%), linear-gradient(180deg, rgba(8,12,16,.98), rgba(13,18,25,.95))' }}>
        <svg viewBox="0 0 400 180" style={{ width: '100%', height: 180, display: 'block' }}>
          <defs>
            <linearGradient id="metroLine" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#3b82f6" />
            </linearGradient>
          </defs>
          <path d="M24 116 C86 92, 132 72, 204 64 S324 80, 372 120" fill="none" stroke="url(#metroLine)" strokeWidth="8" strokeLinecap="round" />
          <path d="M24 116 C86 92, 132 72, 204 64 S324 80, 372 120" fill="none" stroke="rgba(59,130,246,.2)" strokeWidth="20" strokeLinecap="round" />
          {stations.map((station, index) => (
            <g key={station.name}>
              <circle cx={station.x} cy={station.y} r="7" fill="#081018" stroke={index === 1 ? '#10b981' : '#3b82f6'} strokeWidth="3" />
              <text x={station.x} y={station.y + 24} textAnchor="middle" fill="#94a3b8" fontSize="10">
                {station.name}
              </text>
            </g>
          ))}
          <circle cx="118" cy="76" r="6" fill="#10b981">
            <animate attributeName="cx" values="118;208;312;360" dur="7s" repeatCount="indefinite" />
            <animate attributeName="cy" values="76;64;84;114" dur="7s" repeatCount="indefinite" />
          </circle>
        </svg>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10, padding: 12, borderTop: '1px solid rgba(30,45,64,.45)' }}>
          {[
            ['Fleet in motion', '18 revenue trains active across the corridor'],
            ['Weather impact', 'No route restrictions, light rain near city core'],
            ['Crowding pulse', 'Peak crowding forecast after 18:30 at Kaloor'],
          ].map(([label, value]) => (
            <div key={label}>
              <div style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.7px' }}>{label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-1)', marginTop: 4 }}>{value}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function DepotOccupancyGrid() {
  const bays = [
    ['A1', 'rev'], ['A2', 'rev'], ['A3', 'maint'], ['A4', 'rev'], ['A5', 'rev'],
    ['B1', 'rev'], ['B2', 'standby'], ['B3', 'ibl'], ['B4', 'rev'], ['B5', 'rev'],
    ['C1', 'ibl'], ['C2', 'ibl'], ['D1', 'clean'], ['D2', 'empty'], ['M1', 'maint'],
  ] as const

  const palette: Record<string, string> = {
    rev: '#10b981',
    standby: '#f59e0b',
    ibl: '#8b5cf6',
    clean: '#3b82f6',
    maint: '#ef4444',
    empty: '#334155',
  }

  return (
    <Card title="Depot Occupancy Visualization">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 8 }}>
        {bays.map(([bay, state]) => (
          <div key={bay} style={{ padding: '10px 8px', borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--border)', textAlign: 'center' }}>
            <div style={{ fontSize: 9, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>{bay}</div>
            <div style={{ width: 10, height: 10, borderRadius: 3, background: palette[state], margin: '8px auto 6px', boxShadow: `0 0 0 4px ${palette[state]}22` }} />
            <div style={{ fontSize: 10, color: 'var(--text-1)', textTransform: 'capitalize' }}>{state}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function CopilotPanel() {
  const [query, setQuery] = useState('Why was TS-07 sent to IBL tonight?')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<string>('Ask the operational copilot for a recommendation explanation, anomaly context, or depot what-if summary.')

  const quickPrompts = [
    'Why was TS-07 sent to IBL tonight?',
    'Which trainsets are most at risk for tomorrow morning?',
    'Summarize tonight\'s depot conflicts in one paragraph.',
  ]

  const handleAsk = async (prompt: string) => {
    setLoading(true)
    setQuery(prompt)
    try {
      const result = await copilotApi.chat(prompt)
      setResponse(result.response)
    } catch {
      setResponse('The copilot endpoint is unavailable right now, but the fallback guidance is to inspect TS-07 brake wear, monitor TS-22 certification expiry, and protect the standby pool for weather variance.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card title="Operational Copilot">
      <div style={{ display: 'grid', gap: 10 }}>
        <div style={{ fontSize: 11, color: 'var(--text-1)' }}>
          Conversational insights for recommendation explanations, anomaly context, and what-if planning.
        </div>
        <input className="input" value={query} onChange={e => setQuery(e.target.value)} />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {quickPrompts.map(prompt => (
            <button key={prompt} className="btn btn-outline" style={{ fontSize: 10 }} onClick={() => handleAsk(prompt)}>
              {prompt}
            </button>
          ))}
        </div>
        <button className="btn btn-primary" onClick={() => handleAsk(query)} disabled={loading} style={{ width: 'fit-content' }}>
          {loading ? 'Thinking...' : 'Ask Copilot'}
        </button>
        <div style={{ padding: '12px 14px', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 11, color: 'var(--text-1)', lineHeight: 1.6 }}>
          {response}
        </div>
      </div>
    </Card>
  )
}

export default function DashboardPage() {
  const clock = useISTClock()
  const { data: kpis, loading: kpisLoading, refetch: refetchKpis } = useKPIs()
  const { data: fleet, loading: fleetLoading } = useFleet()
  const { alerts, criticalCount } = useAlerts(undefined, false)
  const { plan, running, runOptimizer } = useOptimizer()
  const { connected, latestPlanScore } = useWebSocket()
  const [activeTab, setActiveTab] = useState<'recommendations' | 'fleet'>('recommendations')

  const trendData = [88, 91, 87, 90, 93, 92, 94]
  const recentAlerts = alerts.slice(0, 4)

  const readiness = useMemo(() => {
    if (!kpis) return 92
    const total = kpis.revenue_service_count + kpis.standby_count + kpis.ibl_count + kpis.maintenance_count
    return Math.round(((kpis.revenue_service_count + kpis.standby_count) / Math.max(total, 1)) * 100)
  }, [kpis])

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, animation: 'fade-up .25s ease' }}>
      <SectionHeader
        title="Command Center"
        subtitle={`Nightly induction planning - ${clock} IST`}
        actions={
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontFamily: 'var(--font-mono)', color: connected ? 'var(--emerald)' : 'var(--text-2)', background: connected ? 'var(--emerald-glow)' : 'var(--bg-2)', border: `1px solid ${connected ? 'rgba(16,185,129,.2)' : 'var(--border)'}`, padding: '4px 10px', borderRadius: 20 }}>
              <LivePulse color={connected ? '#10b981' : '#64748b'} />
              {connected ? 'LIVE' : 'OFFLINE'}
            </div>
            <button className="btn btn-outline" onClick={refetchKpis}>Refresh</button>
            <button className="btn btn-primary" onClick={() => runOptimizer()} disabled={running} style={{ opacity: running ? 0.7 : 1 }}>
              {running ? 'Running...' : 'Run Optimizer'}
            </button>
          </>
        }
      />

      <AIInsightTicker plan={plan} latestPlanScore={latestPlanScore} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        {kpisLoading ? (
          Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
        ) : kpis ? (
          <>
            <KPITile label="Fleet Availability" value={`${kpis.fleet_availability_pct}%`} sub="vs yesterday" delta={{ value: '+2.1%', direction: 'up' }} accent="#10b981" sparkData={trendData} />
            <KPITile label="Revenue Service" value={`${kpis.revenue_service_count}/${kpis.revenue_service_count + kpis.standby_count + kpis.ibl_count + kpis.maintenance_count}`} sub="operational tonight" delta={{ value: '+1 from plan', direction: 'up' }} accent="#3b82f6" />
            <KPITile label="AI Confidence" value={`${kpis.ai_confidence_avg.toFixed(0)}%`} sub="optimizer accuracy" delta={{ value: 'High', direction: 'up' }} accent="#8b5cf6" />
            <KPITile label="Shunting Ops" value={kpis.total_shunting_ops_today} sub="tonight's movements" delta={{ value: '-3 optimized', direction: 'up' }} accent="#f59e0b" />
          </>
        ) : null}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr .9fr', gap: 16 }}>
        <Card>
          <div style={{ display: 'flex', gap: 2, marginBottom: 14 }}>
            {(['recommendations', 'fleet'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  padding: '5px 12px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: 'none',
                  fontFamily: 'var(--font-sans)',
                  background: activeTab === tab ? 'var(--bg-4)' : 'transparent',
                  color: activeTab === tab ? 'var(--blue)' : 'var(--text-2)',
                  borderBottom: activeTab === tab ? '1px solid var(--blue)' : '1px solid transparent',
                  transition: 'all .15s',
                }}
              >
                {tab === 'recommendations' ? 'AI Recommendations' : 'Fleet Overview'}
              </button>
            ))}
          </div>

          {activeTab === 'recommendations' ? (
            plan ? (
              <div style={{ maxHeight: 380, overflowY: 'auto' }}>
                {plan.revenue_service.slice(0, 5).map((item, i) => (
                  <AIRecommendationCard key={item.trainset_code} item={item} rank={i + 1} />
                ))}
              </div>
            ) : (
              <EmptyState icon="AI" title="No plan generated yet" description="Run the optimizer to generate AI-ranked induction recommendations." />
            )
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, maxHeight: 380, overflowY: 'auto' }}>
              {fleetLoading
                ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
                : fleet?.slice(0, 6).map(ts => <TrainsetCard key={ts.id} trainset={ts} compact />) ?? <EmptyState icon="TS" title="No fleet data" />}
            </div>
          )}
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <ServiceReadinessCard readiness={readiness} occupiedBays={22} totalBays={25} />
          <WeatherOverlayCard />
          <Card title="Fleet Allocation">
            {kpis ? (
              <FleetAllocationChart
                revenue={kpis.revenue_service_count}
                standby={kpis.standby_count}
                ibl={kpis.ibl_count}
                maintenance={kpis.maintenance_count}
                total={kpis.revenue_service_count + kpis.standby_count + kpis.ibl_count + kpis.maintenance_count}
              />
            ) : (
              <Skeleton height={110} />
            )}
          </Card>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr .9fr', gap: 16 }}>
        <MetroOperationsMap />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <DepotOccupancyGrid />
          <Card title="7-Day Availability Trend">
            <AvailabilityTrendChart data={trendData} />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 9, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(d => <span key={d}>{d}</span>)}
            </div>
          </Card>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '.95fr 1.05fr', gap: 16 }}>
        <CopilotPanel />
        <Card
          title="Active Alerts"
          headerRight={
            criticalCount > 0 ? (
              <span style={{ background: 'rgba(239,68,68,.15)', color: '#ef4444', fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 3 }}>
                {criticalCount} CRITICAL
              </span>
            ) : undefined
          }
        >
          {recentAlerts.length > 0 ? (
            recentAlerts.map(alert => (
              <div key={alert.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 0', borderBottom: '1px solid rgba(30,45,64,.4)' }}>
                <SeverityBadge severity={alert.severity} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-0)', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {alert.title}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>
                    {alert.trainset_code ?? 'Fleet'} · {new Date(alert.created_at).toLocaleTimeString('en-IN', { hour12: false, timeZone: 'Asia/Kolkata' })} IST
                  </div>
                </div>
              </div>
            ))
          ) : (
            <EmptyState icon="OK" title="No active alerts" />
          )}
        </Card>
      </div>

      <Card title="Fleet Mileage Distribution - Last 30 Days" headerRight={<span style={{ fontSize: 10, color: 'var(--text-2)' }}>25 trainsets · km/day</span>}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(25, 1fr)', gap: 3, marginBottom: 8 }}>
          {fleet?.map((ts, i) => {
            const mileage = ts.total_mileage_km ?? 150
            const norm = Math.min(Math.max((mileage - 4000) / 2000, 0), 1)
            const hue = 200 + norm * 40
            const sat = 40 + norm * 40
            const lit = 20 + norm * 30
            return (
              <div
                key={i}
                data-tooltip={`${ts.trainset_code}: ${mileage.toLocaleString()} km`}
                style={{
                  height: 28,
                  borderRadius: 3,
                  cursor: 'pointer',
                  background: `hsl(${hue}, ${sat}%, ${lit}%)`,
                  transition: 'transform .1s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.transform = 'scale(1.15)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.transform = 'scale(1)'
                }}
              />
            )
          }) ?? Array.from({ length: 25 }).map((_, i) => <Skeleton key={i} height={28} />)}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: 'var(--text-2)' }}>
          <span>Low km</span>
          <div style={{ display: 'flex', gap: 2 }}>
            {[0, 1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} style={{ width: 16, height: 10, borderRadius: 2, background: `hsl(${200 + i * 10}, ${40 + i * 10}%, ${20 + i * 5}%)` }} />
            ))}
          </div>
          <span>High km</span>
        </div>
      </Card>
    </div>
  )
}
