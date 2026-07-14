// ============================================================
// KMRL NexusAI — Maintenance Intelligence Page
// Predictive AI · Failure probability · Health scoring
// ============================================================
'use client'

import React, { useState } from 'react'
import { useMaintenancePredictions } from '@/hooks'
import {
  Card, KPITile, SectionHeader, SkeletonCard,
  ErrorState, EmptyState, ConfidenceRing,
} from '@/components/ui'

// ── Risk Color Helpers ────────────────────────────────────────────────────

const RISK_META = {
  critical: { color: '#ef4444', bg: 'rgba(239,68,68,.12)', border: 'rgba(239,68,68,.25)', label: 'CRITICAL' },
  high:     { color: '#f97316', bg: 'rgba(249,115,22,.12)', border: 'rgba(249,115,22,.25)', label: 'HIGH' },
  medium:   { color: '#f59e0b', bg: 'rgba(245,158,11,.12)', border: 'rgba(245,158,11,.25)', label: 'MEDIUM' },
  low:      { color: '#10b981', bg: 'rgba(16,185,129,.12)', border: 'rgba(16,185,129,.25)', label: 'LOW' },
}

function getRiskMeta(risk: number) {
  if (risk > 0.7) return RISK_META.critical
  if (risk > 0.4) return RISK_META.high
  if (risk > 0.2) return RISK_META.medium
  return RISK_META.low
}

// ── Static demo maintenance data ──────────────────────────────────────────

const MAINT_DATA = [
  { code: 'TS-07', system: 'Brake System',      risk: 0.82, pred: 'Wear limit 8–12d',   days: 8,  action: 'IBL Now',   open: 2 },
  { code: 'TS-22', system: 'HVAC Compressor',   risk: 0.71, pred: 'Bearing issue ~10d',  days: 10, action: 'Inspect',   open: 1 },
  { code: 'TS-03', system: 'Door Sensor',        risk: 0.67, pred: 'Sensor fault 15–20d', days: 15, action: 'Schedule',  open: 1 },
  { code: 'TS-11', system: 'Pantograph',         risk: 0.38, pred: 'Minor wear 30d+',     days: 32, action: 'Monitor',   open: 0 },
  { code: 'TS-18', system: 'Bogie',              risk: 0.44, pred: 'Normal wear',          days: 28, action: 'Monitor',   open: 0 },
  { code: 'TS-05', system: 'Brake Pads',         risk: 0.28, pred: 'Replacement 45d',      days: 45, action: 'Plan',      open: 0 },
  { code: 'TS-15', system: 'HVAC Filter',        risk: 0.19, pred: 'Routine service',       days: 60, action: 'Routine',   open: 0 },
  { code: 'TS-20', system: 'Door Motor',         risk: 0.55, pred: 'Wear pattern detected', days: 18, action: 'Schedule',  open: 1 },
]

const JOB_CARDS = [
  { id: 'KMRL-2847', ts: 'TS-03', system: 'Door System',    priority: 'critical', status: 'in_progress', est: '4h',  assignee: 'Rajan K.' },
  { id: 'KMRL-2851', ts: 'TS-07', system: 'Brake System',   priority: 'critical', status: 'open',        est: '6h',  assignee: 'Unassigned' },
  { id: 'KMRL-2855', ts: 'TS-22', system: 'HVAC',           priority: 'critical', status: 'open',        est: '3h',  assignee: 'Suresh P.' },
  { id: 'KMRL-2839', ts: 'TS-20', system: 'Door Motor',     priority: 'high',     status: 'open',        est: '2h',  assignee: 'Arjun M.' },
  { id: 'KMRL-2830', ts: 'TS-11', system: 'Pantograph',     priority: 'medium',   status: 'in_progress', est: '3h',  assignee: 'Krishnan V.' },
  { id: 'KMRL-2821', ts: 'TS-18', system: 'Bogie',          priority: 'medium',   status: 'open',        est: '5h',  assignee: 'Unassigned' },
]

const PRIORITY_META: Record<string, { color: string; bg: string }> = {
  critical: { color: '#ef4444', bg: 'rgba(239,68,68,.12)' },
  high:     { color: '#f97316', bg: 'rgba(249,115,22,.12)' },
  medium:   { color: '#f59e0b', bg: 'rgba(245,158,11,.12)' },
  low:      { color: '#10b981', bg: 'rgba(16,185,129,.12)' },
}

// ── Risk Bar ──────────────────────────────────────────────────────────────

function RiskBar({ value }: { value: number }) {
  const meta = getRiskMeta(value)
  const pct  = Math.round(value * 100)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 80, height: 5, background: 'var(--bg-3)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: meta.color, borderRadius: 3, transition: 'width .5s ease' }} />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: meta.color, width: 34 }}>
        {pct}%
      </span>
    </div>
  )
}

// ── Failure Heatmap ───────────────────────────────────────────────────────

function FailureHeatmap() {
  const systems  = ['Brake', 'HVAC', 'Door', 'Pantograph', 'Bogie']
  const weeks    = ['W−4', 'W−3', 'W−2', 'W−1', 'Now']
  const data: number[][] = [
    [0.2, 0.3, 0.5, 0.7, 0.82],
    [0.3, 0.4, 0.5, 0.6, 0.71],
    [0.1, 0.2, 0.4, 0.5, 0.67],
    [0.1, 0.15, 0.2, 0.3, 0.38],
    [0.2, 0.25, 0.3, 0.4, 0.44],
  ]

  return (
    <div>
      {/* Column headers */}
      <div style={{ display: 'flex', paddingLeft: 80, marginBottom: 6, gap: 4 }}>
        {weeks.map(w => (
          <div key={w} style={{ flex: 1, fontSize: 9, color: 'var(--text-2)', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>{w}</div>
        ))}
      </div>

      {systems.map((sys, si) => (
        <div key={sys} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
          <div style={{ width: 76, fontSize: 10, color: 'var(--text-1)', textAlign: 'right', paddingRight: 8, flexShrink: 0 }}>{sys}</div>
          {data[si].map((val, wi) => {
            const m   = getRiskMeta(val)
            const pct = Math.round(val * 100)
            return (
              <div
                key={wi}
                data-tooltip={`${sys} ${weeks[wi]}: ${pct}% risk`}
                style={{
                  flex: 1, height: 28, borderRadius: 4,
                  background: m.bg, border: `1px solid ${m.border}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 9, fontWeight: 700, color: m.color,
                  fontFamily: 'var(--font-mono)', cursor: 'pointer',
                  transition: 'transform .1s',
                }}
                onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.05)')}
                onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
              >
                {pct}%
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

// ── Wear Distribution Chart ───────────────────────────────────────────────

function WearDistributionChart() {
  const categories  = ['0–20%', '20–40%', '40–60%', '60–80%', '80–100%']
  const counts      = [6, 9, 5, 3, 2]
  const maxC        = Math.max(...counts)
  const colors      = ['#10b981', '#3b82f6', '#f59e0b', '#f97316', '#ef4444']

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 80, marginBottom: 8 }}>
        {counts.map((c, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: colors[i], fontFamily: 'var(--font-mono)' }}>{c}</span>
            <div style={{
              width: '100%', height: Math.round((c / maxC) * 60),
              background: colors[i], borderRadius: '3px 3px 0 0',
              opacity: .8, transition: 'height .4s ease',
            }} />
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {categories.map((cat, i) => (
          <div key={i} style={{ flex: 1, fontSize: 9, color: 'var(--text-2)', textAlign: 'center' }}>{cat}</div>
        ))}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-2)', marginTop: 6 }}>Wear level distribution across 25 trainsets</div>
    </div>
  )
}

// ── MTBF / MTTR Trend ────────────────────────────────────────────────────

function MTBFChart() {
  const months   = ['Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May']
  const mtbf     = [36, 38, 37, 40, 41, 42]
  const mttr     = [4.2, 3.9, 3.7, 3.5, 3.3, 3.2]
  const maxMTBF  = Math.max(...mtbf)
  const h        = 60

  return (
    <div>
      <div style={{ display: 'flex', gap: 14, marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: 'var(--text-1)' }}>
          <span style={{ width: 20, height: 2, background: '#10b981', display: 'inline-block', borderRadius: 1 }} />
          MTBF (days)
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: 'var(--text-1)' }}>
          <span style={{ width: 20, height: 2, background: '#3b82f6', display: 'inline-block', borderRadius: 1, borderTop: '2px dashed #3b82f6' }} />
          MTTR (hours)
        </div>
      </div>

      <svg viewBox={`0 0 300 ${h}`} style={{ width: '100%', height: h, overflow: 'visible' }}>
        {/* MTBF line */}
        {mtbf.map((v, i) => {
          if (i === 0) return null
          const x1 = ((i - 1) / (months.length - 1)) * 300
          const x2 = (i / (months.length - 1)) * 300
          const y1 = h - ((mtbf[i - 1] / maxMTBF) * (h - 10) + 5)
          const y2 = h - ((v / maxMTBF) * (h - 10) + 5)
          return <line key={`mtbf-${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" />
        })}
        {/* MTTR line (scaled differently) */}
        {mttr.map((v, i) => {
          if (i === 0) return null
          const x1 = ((i - 1) / (months.length - 1)) * 300
          const x2 = (i / (months.length - 1)) * 300
          const y1 = h - ((mttr[i - 1] / 5) * (h - 10) + 5)
          const y2 = h - ((v / 5) * (h - 10) + 5)
          return <line key={`mttr-${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="4,2" />
        })}
        {/* Dots */}
        {mtbf.map((v, i) => (
          <circle key={`dot-${i}`} cx={(i / (months.length - 1)) * 300} cy={h - ((v / maxMTBF) * (h - 10) + 5)} r="3" fill="#10b981" />
        ))}
      </svg>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 9, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>
        {months.map(m => <span key={m}>{m}</span>)}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function MaintenancePage() {
  const [activeView, setActiveView] = useState<'predictions' | 'jobs'>('predictions')
  const [selectedSystem, setSelectedSystem] = useState<string>('all')

  const filtered = MAINT_DATA.filter(d =>
    selectedSystem === 'all' || d.system.toLowerCase().includes(selectedSystem)
  )

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, animation: 'fade-up .25s ease' }}>
      <SectionHeader
        title="Maintenance Intelligence"
        subtitle="Predictive AI · XGBoost failure models · Live sensor fusion"
        actions={
          <>
            <button className="btn btn-outline">Schedule Job</button>
            <button className="btn btn-primary">Generate Work Orders</button>
          </>
        }
      />

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        <KPITile label="MTBF (Days)"    value={42}   sub="mean time between failures" delta={{ value: '+4 vs target', direction: 'up' }} accent="#10b981" />
        <KPITile label="MTTR (Hours)"   value="3.2h" sub="mean time to repair"        delta={{ value: '−0.4h improving', direction: 'up' }} accent="#3b82f6" />
        <KPITile label="Open Job Cards" value={11}   sub="3 critical pending"          delta={{ value: '3 critical', direction: 'down' }} accent="#f59e0b" />
        <KPITile label="AI Risk Alerts" value={5}    sub="predictive flags"             delta={{ value: '↑ Review now', direction: 'down' }} accent="#ef4444" />
      </div>

      {/* Top grid: heatmap + wear distribution */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Card title="Predictive Failure Risk Heatmap — 5-Week Trend">
          <FailureHeatmap />
        </Card>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card title="System Wear Distribution">
            <WearDistributionChart />
          </Card>
          <Card title="MTBF / MTTR Trend">
            <MTBFChart />
          </Card>
        </div>
      </div>

      {/* Main table with tabs */}
      <Card>
        <div style={{ display: 'flex', gap: 2, marginBottom: 14 }}>
          {(['predictions', 'jobs'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveView(tab)}
              style={{
                padding: '5px 12px', borderRadius: 6, cursor: 'pointer',
                fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-sans)',
                border: 'none',
                background: activeView === tab ? 'var(--bg-4)' : 'transparent',
                color: activeView === tab ? 'var(--blue)' : 'var(--text-2)',
                borderBottom: activeView === tab ? '1px solid var(--blue)' : '1px solid transparent',
                transition: 'all .15s',
              }}
            >
              {tab === 'predictions' ? '⬡ Predictive Risk Table' : '⊞ Open Job Cards'}
            </button>
          ))}

          {activeView === 'predictions' && (
            <select
              className="select"
              value={selectedSystem}
              onChange={e => setSelectedSystem(e.target.value)}
              style={{ marginLeft: 'auto', width: 150 }}
            >
              <option value="all">All Systems</option>
              <option value="brake">Brake</option>
              <option value="hvac">HVAC</option>
              <option value="door">Door</option>
              <option value="pantograph">Pantograph</option>
              <option value="bogie">Bogie</option>
            </select>
          )}
        </div>

        {activeView === 'predictions' ? (
          <table className="data-table" data-cy="maintenance-table">
            <thead>
              <tr>
                <th>Trainset</th>
                <th>System</th>
                <th>Risk Score</th>
                <th>AI Prediction</th>
                <th>Days to Service</th>
                <th>Open Jobs</th>
                <th>Recommended Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(row => {
                const riskMeta = getRiskMeta(row.risk)
                const pct      = Math.round(row.risk * 100)
                return (
                  <tr key={row.code} data-cy={pct > 70 ? 'risk-critical' : 'risk-row'}>
                    <td>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{row.code}</span>
                    </td>
                    <td style={{ color: 'var(--text-1)' }}>{row.system}</td>
                    <td data-cy="risk-level">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <RiskBar value={row.risk} />
                      </div>
                    </td>
                    <td style={{ color: 'var(--text-1)', fontSize: 11 }}>{row.pred}</td>
                    <td>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontWeight: 700,
                        color: row.days <= 10 ? '#ef4444' : row.days <= 20 ? '#f59e0b' : '#10b981',
                      }}>
                        {row.days}d
                      </span>
                    </td>
                    <td>
                      {row.open > 0
                        ? <span style={{ color: '#ef4444', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{row.open} open</span>
                        : <span style={{ color: 'var(--text-2)' }}>—</span>
                      }
                    </td>
                    <td>
                      <span style={{
                        fontSize: 10, padding: '3px 8px', borderRadius: 4, fontWeight: 600,
                        background: riskMeta.bg, color: riskMeta.color,
                        border: `1px solid ${riskMeta.border}`,
                      }}>
                        {row.action}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Job Card</th>
                <th>Trainset</th>
                <th>System</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Est. Hours</th>
                <th>Assigned To</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {JOB_CARDS.map(job => {
                const pm = PRIORITY_META[job.priority] ?? PRIORITY_META.medium
                const statusColor = job.status === 'in_progress' ? '#3b82f6' : 'var(--text-2)'
                return (
                  <tr key={job.id}>
                    <td><span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{job.id}</span></td>
                    <td><span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{job.ts}</span></td>
                    <td style={{ color: 'var(--text-1)' }}>{job.system}</td>
                    <td>
                      <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 3, fontWeight: 600, background: pm.bg, color: pm.color }}>
                        {job.priority}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontSize: 11, color: statusColor, fontWeight: 500 }}>
                        {job.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-1)' }}>{job.est}</td>
                    <td style={{ color: job.assignee === 'Unassigned' ? '#ef4444' : 'var(--text-1)', fontSize: 11 }}>{job.assignee}</td>
                    <td>
                      <button className="btn btn-outline" style={{ fontSize: 10, padding: '3px 8px' }}>Edit</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
