// ============================================================
// KMRL NexusAI — AI Scheduler Page
// Interactive timeline + constraint panel + what-if controls
// ============================================================
'use client'

import React, { useCallback, useState } from 'react'
import { useFleet, useOptimizer, useSimulation } from '@/hooks'
import { certsApi } from '@/lib/api'
import {
  Card, EmptyState, ErrorState, KPITile,
  SectionHeader, SeverityBadge, SkeletonCard,
} from '@/components/ui'
import AIRecommendationCard from '@/components/ai/AIRecommendationCard'

// ── Timeline Block ────────────────────────────────────────────────────────

const BLOCK_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  revenue_service: { bg: 'rgba(16,185,129,.15)', border: '#10b981', text: '#10b981' },
  standby:         { bg: 'rgba(245,158,11,.15)', border: '#f59e0b', text: '#f59e0b' },
  ibl:             { bg: 'rgba(139,92,246,.15)', border: '#8b5cf6', text: '#8b5cf6' },
  maintenance:     { bg: 'rgba(239,68,68,.15)',  border: '#ef4444', text: '#ef4444' },
  cleaning:        { bg: 'rgba(59,130,246,.15)', border: '#3b82f6', text: '#3b82f6' },
  stabling:        { bg: 'rgba(51,65,85,.3)',    border: '#475569', text: '#475569' },
}

interface ScheduleBlock {
  id: string
  trainset: string
  type: string
  label: string
  startHour: number   // 0–24
  endHour: number
  bay?: string
  confidence?: number
}

const DEMO_BLOCKS: ScheduleBlock[] = [
  { id: '1',  trainset: 'TS-01', type: 'revenue_service', label: 'SMA Line',        startHour: 6,  endHour: 20, confidence: 96 },
  { id: '2',  trainset: 'TS-01', type: 'cleaning',        label: 'Deep Clean',       startHour: 21, endHour: 23 },
  { id: '3',  trainset: 'TS-02', type: 'revenue_service', label: 'SLV Line',        startHour: 7,  endHour: 19, confidence: 91 },
  { id: '4',  trainset: 'TS-02', type: 'standby',         label: 'Standby Ready',   startHour: 20, endHour: 23 },
  { id: '5',  trainset: 'TS-03', type: 'maintenance',     label: 'Brake Service',   startHour: 0,  endHour: 7 },
  { id: '6',  trainset: 'TS-03', type: 'revenue_service', label: 'CUSAT Express',   startHour: 8,  endHour: 20, confidence: 88 },
  { id: '7',  trainset: 'TS-07', type: 'ibl',             label: 'IBL Inspection',  startHour: 0,  endHour: 10 },
  { id: '8',  trainset: 'TS-14', type: 'revenue_service', label: 'Aluva–Petta',     startHour: 6,  endHour: 22, confidence: 96 },
  { id: '9',  trainset: 'TS-19', type: 'standby',         label: 'Standby',         startHour: 8,  endHour: 14 },
  { id: '10', trainset: 'TS-19', type: 'revenue_service', label: 'SMA Express',     startHour: 15, endHour: 22, confidence: 84 },
  { id: '11', trainset: 'TS-22', type: 'maintenance',     label: 'Cert Renewal',    startHour: 21, endHour: 24 },
]

// ── Timeline Row ──────────────────────────────────────────────────────────

function TimelineRow({ trainset, blocks, selectedId, onSelect }: {
  trainset: string
  blocks: ScheduleBlock[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, height: 34, marginBottom: 3 }}>
      <span style={{
        fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
        color: 'var(--text-1)', width: 56, flexShrink: 0, paddingRight: 8,
      }}>
        {trainset}
      </span>

      <div style={{
        flex: 1, height: 26, background: 'var(--bg-2)', borderRadius: 5,
        position: 'relative', overflow: 'hidden', border: '1px solid var(--border)',
      }}>
        {blocks.map(block => {
          const left  = (block.startHour / 24) * 100
          const width = ((block.endHour - block.startHour) / 24) * 100
          const c     = BLOCK_COLORS[block.type] ?? BLOCK_COLORS.stabling
          const selected = selectedId === block.id
          return (
            <div
              key={block.id}
              onClick={() => onSelect(block.id)}
              style={{
                position: 'absolute', top: 3,
                left: `${left}%`, width: `${width}%`, height: 20,
                background: c.bg,
                border: `1px solid ${selected ? c.border : c.border + '80'}`,
                borderRadius: 3,
                display: 'flex', alignItems: 'center', padding: '0 6px',
                cursor: 'pointer', overflow: 'hidden', whiteSpace: 'nowrap',
                transition: 'filter .12s',
                boxShadow: selected ? `0 0 0 1px ${c.border}` : 'none',
              }}
              onMouseEnter={e => (e.currentTarget.style.filter = 'brightness(1.2)')}
              onMouseLeave={e => (e.currentTarget.style.filter = 'brightness(1)')}
            >
              <span style={{ fontSize: 10, fontWeight: 600, color: c.text, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {block.label}
              </span>
              {block.confidence && (
                <span style={{ marginLeft: 'auto', fontSize: 9, color: c.text, fontFamily: 'var(--font-mono)', opacity: .8 }}>
                  {block.confidence}%
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Time Ruler ────────────────────────────────────────────────────────────

function TimeRuler() {
  const hours = Array.from({ length: 13 }, (_, i) => i * 2)
  return (
    <div style={{ display: 'flex', paddingLeft: 56, marginBottom: 6 }}>
      <div style={{ flex: 1, display: 'flex', justifyContent: 'space-between' }}>
        {hours.map(h => (
          <span key={h} style={{
            fontSize: 9, color: 'var(--text-2)', fontFamily: 'var(--font-mono)',
            textAlign: 'center',
          }}>
            {String(h).padStart(2, '0')}:00
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Cert Health Panel ─────────────────────────────────────────────────────

const CERT_DATA = [
  { name: 'Rolling Stock Fitness', days: 42,  status: 'valid' as const },
  { name: 'Signalling Clearance',  days: 18,  status: 'valid' as const },
  { name: 'Telecom Clearance',     days: 7,   status: 'expiring_soon' as const },
  { name: 'Brake Health Cert',     days: -3,  status: 'expired' as const },
  { name: 'HVAC Certificate',      days: 31,  status: 'valid' as const },
  { name: 'Door System Cert',      days: 12,  status: 'expiring_soon' as const },
]

function CertHealthPanel() {
  const statusMeta = {
    valid:         { color: '#10b981', bg: 'rgba(16,185,129,.1)',  label: 'Valid'    },
    expiring_soon: { color: '#f59e0b', bg: 'rgba(245,158,11,.1)', label: 'Expiring' },
    expired:       { color: '#ef4444', bg: 'rgba(239,68,68,.1)',   label: 'Expired'  },
  }

  return (
    <div>
      {CERT_DATA.map(cert => {
        const m = statusMeta[cert.status]
        return (
          <div key={cert.name} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '7px 0', borderBottom: '1px solid rgba(30,45,64,.4)',
          }}>
            <span style={{ fontSize: 11, color: 'var(--text-1)', flex: 1 }}>{cert.name}</span>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 11,
              color: cert.days < 0 ? '#ef4444' : cert.days <= 7 ? '#f59e0b' : 'var(--text-2)',
              width: 48, textAlign: 'right',
            }}>
              {cert.days < 0 ? 'EXPD' : `${cert.days}d`}
            </span>
            <span style={{
              fontSize: 10, fontWeight: 600, padding: '2px 7px',
              borderRadius: 3, background: m.bg, color: m.color,
            }}>
              {m.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── What-If Controls ──────────────────────────────────────────────────────

function WhatIfPanel({ onRunSimulation, loading }: {
  onRunSimulation: (scenario: string, params: Record<string, unknown>) => void
  loading: boolean
}) {
  const [scenario, setScenario] = useState('shunting_optimization')
  const [revenueTarget, setRevenueTarget] = useState(18)
  const [delayHours, setDelayHours] = useState(4)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ fontSize: 11, color: 'var(--text-1)' }}>
        Model hypothetical changes to tonight's plan and see their impact before committing.
      </div>

      <div>
        <label style={{ fontSize: 10, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: 4 }}>
          Scenario
        </label>
        <select className="select" value={scenario} onChange={e => setScenario(e.target.value)} style={{ width: '100%' }}>
          <option value="shunting_optimization">Shunting Optimization</option>
          <option value="maintenance_delay">Maintenance Delay Cascade</option>
          <option value="emergency_withdrawal">Emergency Withdrawal</option>
          <option value="bay_reallocation">Bay Reallocation</option>
          <option value="cleaning_bottleneck">Cleaning Bottleneck</option>
        </select>
      </div>

      {scenario === 'maintenance_delay' && (
        <div>
          <label style={{ fontSize: 10, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: 4 }}>
            Delay Hours
          </label>
          <input
            type="range" min={1} max={12} value={delayHours}
            onChange={e => setDelayHours(Number(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--blue)' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-2)' }}>
            <span>1h</span><span style={{ color: 'var(--amber)', fontWeight: 600 }}>{delayHours}h selected</span><span>12h</span>
          </div>
        </div>
      )}

      <div>
        <label style={{ fontSize: 10, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: 4 }}>
          Revenue Target Override
        </label>
        <input className="input" type="number" min={10} max={25} value={revenueTarget}
          onChange={e => setRevenueTarget(Number(e.target.value))} />
      </div>

      <button
        className="btn btn-primary"
        onClick={() => onRunSimulation(scenario, { delay_hours: delayHours, revenue_target: revenueTarget })}
        disabled={loading}
        style={{ width: '100%', justifyContent: 'center' }}
      >
        {loading ? '⟳ Simulating…' : '⚡ Run What-If'}
      </button>
    </div>
  )
}

// ── Simulation Result ─────────────────────────────────────────────────────

function SimulationResultPanel({ result }: { result: NonNullable<ReturnType<typeof useSimulation>['result']> }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{
        padding: '10px 12px', background: 'rgba(59,130,246,.06)',
        border: '1px solid rgba(59,130,246,.2)', borderRadius: 7,
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--blue)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.6px' }}>
          {result.scenario_name.replace(/_/g, ' ').toUpperCase()}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {[
            ['Shunting Ops', `${result.optimized_shunting_ops} (was ${result.baseline_shunting_ops})`],
            ['Reduction', `${result.reduction_pct.toFixed(1)}%`],
            ['Total Time', `${result.total_time_mins.toFixed(0)} min`],
            ['Fleet Ready', `${result.fleet_readiness_pct.toFixed(1)}%`],
          ].map(([label, value]) => (
            <div key={label}>
              <div style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.5px' }}>{label}</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-0)', fontFamily: 'var(--font-mono)' }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {result.alerts.length > 0 && (
        <div>
          {result.alerts.slice(0, 3).map((a, i) => (
            <div key={i} style={{ fontSize: 10, color: 'var(--amber)', marginBottom: 3 }}>⚠ {a}</div>
          ))}
        </div>
      )}

      {Object.keys(result.kpis).length > 0 && (
        <div style={{ fontSize: 10, color: 'var(--text-2)' }}>
          {Object.entries(result.kpis).map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span>{k.replace(/_/g, ' ')}</span>
              <span style={{ color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>{String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function SchedulerPage() {
  const { plan, running: optimizerRunning, runOptimizer } = useOptimizer()
  const { result: simResult, running: simRunning, runScenario } = useSimulation()
  const [selectedBlock, setSelectedBlock] = useState<string | null>(null)
  const [whatIfMode, setWhatIfMode] = useState(false)

  const trainsets = [...new Set(DEMO_BLOCKS.map(b => b.trainset))]
  const selectedBlockData = DEMO_BLOCKS.find(b => b.id === selectedBlock)

  const handleRunSimulation = useCallback(async (scenario: string, params: Record<string, unknown>) => {
    await runScenario(scenario, params)
  }, [runScenario])

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, animation: 'fade-up .25s ease' }}>
      <SectionHeader
        title="AI Induction Scheduler"
        subtitle="24-hour timeline · Constraint-aware · Real-time optimization"
        actions={
          <>
            <button
              className={`btn ${whatIfMode ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setWhatIfMode(v => !v)}
            >
              ◈ What-If Mode {whatIfMode ? 'ON' : ''}
            </button>
            <button
              className="btn btn-primary"
              onClick={() => runOptimizer()}
              disabled={optimizerRunning}
            >
              {optimizerRunning ? '⟳ Optimizing…' : '⚡ Auto-Optimize'}
            </button>
          </>
        }
      />

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        <KPITile label="Revenue Trains"  value={plan ? plan.revenue_service.length : 18} sub="tonight" accent="#10b981" />
        <KPITile label="Optimizer Score" value={plan ? `${plan.score.toFixed(1)}` : '—'} sub="/100" accent="#3b82f6" />
        <KPITile label="Shunting Ops"    value={plan ? plan.total_shunting_ops : 14}  sub="movements" accent="#f59e0b" />
        <KPITile label="SLA Compliance"  value={plan ? `${plan.sla_compliance_pct.toFixed(0)}%` : '97%'} accent="#10b981" />
      </div>

      {/* Main grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 16 }}>

        {/* Timeline board */}
        <Card title="24-Hour Induction Timeline — Tonight">
          <TimeRuler />
          <div style={{ maxHeight: 320, overflowY: 'auto' }}>
            {trainsets.map(ts => (
              <TimelineRow
                key={ts}
                trainset={ts}
                blocks={DEMO_BLOCKS.filter(b => b.trainset === ts)}
                selectedId={selectedBlock}
                onSelect={setSelectedBlock}
              />
            ))}
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', gap: 14, marginTop: 12, flexWrap: 'wrap' }}>
            {Object.entries(BLOCK_COLORS).map(([type, c]) => (
              <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: 'var(--text-2)' }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: c.bg, border: `1px solid ${c.border}` }} />
                {type.replace('_', ' ')}
              </div>
            ))}
          </div>

          {/* Selected block detail */}
          {selectedBlockData && (
            <div style={{
              marginTop: 12, padding: '10px 12px',
              background: 'var(--bg-3)', borderRadius: 7,
              border: `1px solid ${BLOCK_COLORS[selectedBlockData.type]?.border ?? 'var(--border)'}40`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 13 }}>{selectedBlockData.trainset}</span>
                <span style={{ fontSize: 11, color: BLOCK_COLORS[selectedBlockData.type]?.text }}>{selectedBlockData.label}</span>
                <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>
                  {String(selectedBlockData.startHour).padStart(2, '0')}:00 — {String(selectedBlockData.endHour).padStart(2, '0')}:00
                </span>
              </div>
              {selectedBlockData.confidence && (
                <div style={{ fontSize: 11, color: 'var(--text-1)' }}>
                  AI confidence: <span style={{ color: '#10b981', fontWeight: 600 }}>{selectedBlockData.confidence}%</span>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {whatIfMode ? (
            <Card title="⚡ What-If Simulation">
              <WhatIfPanel onRunSimulation={handleRunSimulation} loading={simRunning} />
              {simResult && (
                <>
                  <div style={{ height: 1, background: 'var(--border)', margin: '12px 0' }} />
                  <SimulationResultPanel result={simResult} />
                </>
              )}
            </Card>
          ) : (
            <Card title="Constraint Conflicts">
              {[
                { type: 'warning' as const, msg: 'TS-07 & TS-19 bay conflict at 22:30 — rescheduled' },
                { type: 'critical' as const, msg: 'TS-22 fitness cert expiring in 2 days — IBL needed' },
                { type: 'info' as const,    msg: 'TS-03 maintenance window extends to 04:00' },
              ].map((c, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 8,
                  padding: '8px 0', borderBottom: '1px solid rgba(30,45,64,.4)',
                }}>
                  <SeverityBadge severity={c.type} />
                  <span style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.4 }}>{c.msg}</span>
                </div>
              ))}
            </Card>
          )}

          <Card title="Certificate Health">
            <CertHealthPanel />
          </Card>
        </div>
      </div>

      {/* AI Recommendations */}
      {plan && (
        <Card title="AI Induction Recommendations">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {plan.revenue_service.slice(0, 4).map((item, i) => (
              <AIRecommendationCard key={item.trainset_code} item={item} rank={i + 1} />
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
