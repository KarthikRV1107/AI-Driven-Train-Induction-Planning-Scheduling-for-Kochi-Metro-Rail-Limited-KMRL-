// ============================================================
// KMRL NexusAI — Depot Digital Twin Page
// Interactive SVG layout · Bay occupancy · Shunting sim
// ============================================================
'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useDepotLayout, useSimulation } from '@/hooks'
import { DepotBay } from '@/lib/api'
import { Card, KPITile, SectionHeader } from '@/components/ui'

// ── Color helpers ─────────────────────────────────────────────────────────

const BAY_COLORS = {
  revenue_service: { fill: 'rgba(16,185,129,.2)',  stroke: '#10b981', text: '#10b981'  },
  standby:         { fill: 'rgba(245,158,11,.2)',  stroke: '#f59e0b', text: '#f59e0b'  },
  ibl:             { fill: 'rgba(139,92,246,.2)',  stroke: '#8b5cf6', text: '#8b5cf6'  },
  maintenance:     { fill: 'rgba(239,68,68,.2)',   stroke: '#ef4444', text: '#ef4444'  },
  cleaning:        { fill: 'rgba(59,130,246,.2)',  stroke: '#3b82f6', text: '#3b82f6'  },
  stabling:        { fill: 'rgba(30,45,64,.5)',    stroke: '#334155', text: '#475569'  },
  empty:           { fill: 'rgba(18,25,34,.6)',    stroke: '#1e2d40', text: '#334155'  },
}

// Static depot layout — matches backend simulation engine
const DEPOT_BAYS = [
  // Row A — stabling (9 bays)
  ...Array.from({ length: 9 }, (_, i) => ({
    code: `A${i + 1}`, row: 'A', col: i,
    x: 30 + i * 64, y: 28, w: 56, h: 26,
    trainset: i < 9 ? `TS-${String(i + 1).padStart(2, '0')}` : null,
    status: ['revenue_service', 'revenue_service', 'maintenance', 'revenue_service', 'revenue_service', 'revenue_service', 'ibl', 'revenue_service', 'revenue_service'][i] as string,
  })),
  // Row B — stabling (9 bays)
  ...Array.from({ length: 9 }, (_, i) => ({
    code: `B${i + 1}`, row: 'B', col: i,
    x: 30 + i * 64, y: 80, w: 56, h: 26,
    trainset: i < 9 ? `TS-${String(i + 10).padStart(2, '0')}` : null,
    status: ['revenue_service', 'revenue_service', 'revenue_service', 'revenue_service', 'revenue_service', 'revenue_service', 'standby', 'ibl', 'revenue_service'][i] as string,
  })),
  // Row C — IBL (4 bays)
  ...Array.from({ length: 4 }, (_, i) => ({
    code: `C${i + 1}`, row: 'C', col: i,
    x: 30 + i * 64, y: 132, w: 56, h: 26,
    trainset: i < 2 ? `TS-${String(i + 19).padStart(2, '0')}` : null,
    status: i < 2 ? 'ibl' : 'empty',
  })),
  // Row D — Cleaning (3 bays)
  ...Array.from({ length: 3 }, (_, i) => ({
    code: `D${i + 1}`, row: 'D', col: i,
    x: 30 + i * 64, y: 184, w: 56, h: 26,
    trainset: i < 1 ? 'TS-23' : null,
    status: i < 1 ? 'cleaning' : 'empty',
  })),
  // Row M — Maintenance (3 bays)
  ...Array.from({ length: 3 }, (_, i) => ({
    code: `M${i + 1}`, row: 'M', col: i,
    x: 30 + i * 64, y: 236, w: 56, h: 26,
    trainset: i < 1 ? 'TS-24' : null,
    status: i < 1 ? 'maintenance' : 'empty',
  })),
]

// ── Depot SVG ─────────────────────────────────────────────────────────────

interface DepotSVGProps {
  selectedBay: string | null
  onBayClick: (code: string) => void
  animatingBays: Set<string>
}

function DepotSVG({ selectedBay, onBayClick, animatingBays }: DepotSVGProps) {
  const rowLabels = [
    { row: 'A', y: 28,  label: 'ROW A — Stabling'   },
    { row: 'B', y: 80,  label: 'ROW B — Stabling'   },
    { row: 'C', y: 132, label: 'ROW C — IBL'         },
    { row: 'D', y: 184, label: 'ROW D — Cleaning'    },
    { row: 'M', y: 236, label: 'ROW M — Maintenance' },
  ]

  return (
    <svg
      data-cy="depot-svg"
      viewBox="0 0 640 280"
      style={{ width: '100%', height: 'auto' }}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Shed boundary */}
      <rect x="8" y="8" width="624" height="264" rx="5" fill="none" stroke="#1e2d40" strokeWidth="1" />

      {/* Header label */}
      <text x="320" y="5" fill="#334155" fontSize="8" textAnchor="middle"
        fontFamily="'Space Grotesk',sans-serif" fontWeight="600" letterSpacing="1.5">
        MUTTOM DEPOT — DIGITAL TWIN
      </text>

      {/* Main run-around track */}
      <line x1="20" y1="272" x2="620" y2="272" stroke="#253548" strokeWidth="2" />
      <line x1="20" y1="268" x2="620" y2="268" stroke="#1e2d40" strokeWidth="1" strokeDasharray="5,4" />

      {/* Row labels */}
      {rowLabels.map(r => (
        <text key={r.row} x="6" y={r.y + 17} fill="#334155" fontSize="7"
          fontFamily="'Space Grotesk',sans-serif" fontWeight="500"
          transform={`rotate(-90, 6, ${r.y + 17})`}>
          {r.label}
        </text>
      ))}

      {/* Track lines per row */}
      {rowLabels.map(r => (
        <React.Fragment key={`track-${r.row}`}>
          <line x1="20" y1={r.y + 26} x2="620" y2={r.y + 26} stroke="#1e2d40" strokeWidth="1" />
          <line x1="20" y1={r.y}      x2="620" y2={r.y}      stroke="#1e2d40" strokeWidth="1" />
        </React.Fragment>
      ))}

      {/* Vertical drop lines */}
      {DEPOT_BAYS.filter(b => b.trainset).map(bay => (
        <line key={`drop-${bay.code}`}
          x1={bay.x + bay.w / 2} y1={bay.y + bay.h}
          x2={bay.x + bay.w / 2} y2={272}
          stroke="#1e2d40" strokeWidth="1" strokeDasharray="3,3"
        />
      ))}

      {/* Bay slots */}
      {DEPOT_BAYS.map(bay => {
        const status  = bay.status || 'empty'
        const c       = BAY_COLORS[status as keyof typeof BAY_COLORS] ?? BAY_COLORS.empty
        const sel     = selectedBay === bay.code
        const anim    = animatingBays.has(bay.code)
        const opacity = anim ? .5 : 1

        return (
          <g
            key={bay.code}
            className="bay-slot"
            style={{ cursor: 'pointer', opacity }}
            onClick={() => onBayClick(bay.code)}
          >
            <rect
              x={bay.x} y={bay.y} width={bay.w} height={bay.h} rx="3"
              fill={c.fill}
              stroke={sel ? c.stroke : c.stroke + '80'}
              strokeWidth={sel ? 1.5 : 1}
              style={{ transition: 'all .15s' }}
            />
            {/* Bay code */}
            <text x={bay.x + 4} y={bay.y + 8} fill="#475569" fontSize="6"
              fontFamily="'JetBrains Mono',monospace" fontWeight="500">
              {bay.code}
            </text>
            {/* Trainset label */}
            {bay.trainset && (
              <text x={bay.x + bay.w / 2} y={bay.y + bay.h / 2 + 4}
                textAnchor="middle" fill={c.text} fontSize="8"
                fontFamily="'JetBrains Mono',monospace" fontWeight="700">
                {bay.trainset}
              </text>
            )}
            {/* Selection ring */}
            {sel && (
              <rect x={bay.x - 1} y={bay.y - 1} width={bay.w + 2} height={bay.h + 2} rx="4"
                fill="none" stroke={c.stroke} strokeWidth="2" opacity=".6"
              />
            )}
            {/* Animate indicator */}
            {anim && (
              <rect x={bay.x} y={bay.y} width={bay.w} height={bay.h} rx="3"
                fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="4,2">
                <animate attributeName="stroke-dashoffset" from="0" to="12" dur="0.8s" repeatCount="indefinite" />
              </rect>
            )}
          </g>
        )
      })}

      {/* Shunting path overlay (demo) */}
      <path d="M 143,54 L 143,268 L 207,268 L 207,106" fill="none" stroke="#f59e0b"
        strokeWidth="1.5" strokeDasharray="5,3" opacity=".4">
        <animate attributeName="stroke-dashoffset" from="0" to="24" dur="1s" repeatCount="indefinite" />
      </path>
      <circle cx="207" cy="106" r="3" fill="#f59e0b" opacity=".6" />
      <text x="160" y="264" fill="#f59e0b" fontSize="7" fontFamily="'Space Grotesk',sans-serif" opacity=".7">
        Shunt TS-03 → M1
      </text>
    </svg>
  )
}

// ── Bay Detail Panel ──────────────────────────────────────────────────────

function BayDetailPanel({ bayCode, onClose }: { bayCode: string; onClose: () => void }) {
  const bay = DEPOT_BAYS.find(b => b.code === bayCode)
  if (!bay) return null
  const c = BAY_COLORS[bay.status as keyof typeof BAY_COLORS] ?? BAY_COLORS.empty

  return (
    <div style={{
      padding: '14px', background: 'var(--bg-2)',
      border: `1px solid ${c.stroke}40`, borderRadius: 8,
      animation: 'fade-up .15s ease',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 15, color: c.text }}>{bayCode}</span>
          <span style={{ fontSize: 10, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.5px' }}>
            {bay.row === 'C' ? 'IBL Bay' : bay.row === 'D' ? 'Cleaning Bay' : bay.row === 'M' ? 'Maintenance Bay' : 'Stabling Bay'}
          </span>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-2)', cursor: 'pointer', fontSize: 16 }}>×</button>
      </div>

      {bay.trainset ? (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
            {[
              ['Trainset',  bay.trainset],
              ['Status',    bay.status?.replace('_', ' ') ?? '—'],
              ['Bay Type',  bay.row === 'C' ? 'IBL' : bay.row === 'D' ? 'Cleaning' : bay.row === 'M' ? 'Maintenance' : 'Stabling'],
              ['Position',  `Row ${bay.row}, Slot ${bay.col + 1}`],
            ].map(([label, value]) => (
              <div key={label} style={{ padding: '7px 10px', background: 'var(--bg-1)', borderRadius: 5, border: '1px solid var(--border)' }}>
                <div style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-0)', fontFamily: 'var(--font-mono)' }}>{value}</div>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-outline" style={{ flex: 1, justifyContent: 'center', fontSize: 10 }}>View Trainset</button>
            <button className="btn btn-outline" style={{ flex: 1, justifyContent: 'center', fontSize: 10 }}>Plan Shunt</button>
          </div>
        </>
      ) : (
        <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--text-2)', fontSize: 11 }}>
          Bay is empty — available for assignment
        </div>
      )}
    </div>
  )
}

// ── Legend ────────────────────────────────────────────────────────────────

function DepotLegend() {
  const items = [
    { label: 'Revenue Service', color: '#10b981' },
    { label: 'Standby',         color: '#f59e0b' },
    { label: 'IBL',             color: '#8b5cf6' },
    { label: 'Maintenance',     color: '#ef4444' },
    { label: 'Cleaning',        color: '#3b82f6' },
    { label: 'Empty',           color: '#334155' },
  ]
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      {items.map(i => (
        <div key={i.label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: 'var(--text-1)' }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: i.color + '30', border: `1px solid ${i.color}`, display: 'inline-block' }} />
          {i.label}
        </div>
      ))}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function DepotPage() {
  const [selectedBay, setSelectedBay]     = useState<string | null>(null)
  const [animatingBays, setAnimatingBays] = useState<Set<string>>(new Set())
  const { result: simResult, running: simRunning, runScenario } = useSimulation()

  const occupiedBays   = DEPOT_BAYS.filter(b => b.trainset).length
  const totalBays      = DEPOT_BAYS.length
  const revenueBays    = DEPOT_BAYS.filter(b => b.status === 'revenue_service').length
  const iblBays        = DEPOT_BAYS.filter(b => b.status === 'ibl').length

  const handleSimulate = useCallback(async () => {
    // Animate a few bays during simulation
    const animated = new Set(['A3', 'B7', 'C1', 'M1'])
    setAnimatingBays(animated)
    await runScenario('shunting_optimization')
    setAnimatingBays(new Set())
  }, [runScenario])

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, animation: 'fade-up .25s ease' }}>
      <SectionHeader
        title="Depot Digital Twin"
        subtitle="Muttom Depot · 25 stabling positions · Live bay occupancy"
        actions={
          <>
            <button className="btn btn-outline" onClick={handleSimulate} disabled={simRunning}>
              {simRunning ? '⟳ Simulating…' : '▶ Simulate Shunt'}
            </button>
            <button className="btn btn-primary">Optimize Layout</button>
          </>
        }
      />

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        <KPITile label="Occupied Bays"   value={`${occupiedBays}/${totalBays}`} sub={`${Math.round(occupiedBays/totalBays*100)}% utilization`} accent="#3b82f6" />
        <KPITile label="Revenue Bays"    value={revenueBays}  sub="active tonight"  accent="#10b981" />
        <KPITile label="IBL Bays"        value={iblBays}      sub="under inspection" accent="#8b5cf6" />
        <KPITile label="Shunting Ops"    value={simResult ? simResult.optimized_shunting_ops : 14}
          sub={simResult ? `−${simResult.baseline_shunting_ops - simResult.optimized_shunting_ops} optimized` : 'tonight'}
          delta={simResult ? { value: `-${(simResult.reduction_pct).toFixed(0)}%`, direction: 'up' } : undefined}
          accent="#f59e0b"
        />
      </div>

      {/* Main layout grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 16 }}>
        {/* SVG depot */}
        <Card title="Muttom Depot — Bay Occupancy Map" headerRight={
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#10b981' }}>
            {occupiedBays}/{totalBays} occupied
          </span>
        }>
          <DepotSVG
            selectedBay={selectedBay}
            onBayClick={setSelectedBay}
            animatingBays={animatingBays}
          />
          <div style={{ marginTop: 10 }}>
            <DepotLegend />
          </div>
        </Card>

        {/* Right: bay detail + sim result */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {selectedBay ? (
            <BayDetailPanel bayCode={selectedBay} onClose={() => setSelectedBay(null)} />
          ) : (
            <div style={{
              padding: 14, background: 'var(--bg-2)', border: '1px solid var(--border)',
              borderRadius: 8, fontSize: 11, color: 'var(--text-2)', textAlign: 'center',
            }}>
              Click any bay on the map to view trainset details
            </div>
          )}

          {simResult && (
            <Card title="Simulation Result">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  ['Baseline ops',   simResult.baseline_shunting_ops],
                  ['Optimized ops',  simResult.optimized_shunting_ops],
                  ['Time saved',     `${simResult.kpis?.time_saved_mins ?? 0} min`],
                  ['Fleet readiness', `${simResult.fleet_readiness_pct.toFixed(1)}%`],
                  ['Conflicts',      `${simResult.conflicts_detected} detected`],
                ].map(([label, value]) => (
                  <div key={String(label)} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--text-2)' }}>{label}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-0)', fontWeight: 600 }}>{String(value)}</span>
                  </div>
                ))}
              </div>

              {simResult.alerts.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  {simResult.alerts.slice(0, 2).map((a, i) => (
                    <div key={i} style={{ fontSize: 10, color: '#f59e0b', marginBottom: 3 }}>⚠ {a}</div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* Row utilization bars */}
          <Card title="Bay Row Utilization">
            {[
              { row: 'Row A (Stabling)', used: 9, total: 9, color: '#10b981' },
              { row: 'Row B (Stabling)', used: 9, total: 9, color: '#10b981' },
              { row: 'Row C (IBL)',      used: 2, total: 4, color: '#8b5cf6' },
              { row: 'Row D (Cleaning)', used: 1, total: 3, color: '#3b82f6' },
              { row: 'Row M (Maint.)',   used: 1, total: 3, color: '#ef4444' },
            ].map(r => (
              <div key={r.row} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-2)', marginBottom: 3 }}>
                  <span>{r.row}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: r.color }}>{r.used}/{r.total}</span>
                </div>
                <div style={{ height: 5, background: 'var(--bg-3)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${(r.used / r.total) * 100}%`, height: '100%', background: r.color, borderRadius: 3, transition: 'width .5s ease' }} />
                </div>
              </div>
            ))}
          </Card>
        </div>
      </div>

      {/* Shunting move list */}
      {simResult?.shunt_moves && simResult.shunt_moves.length > 0 && (
        <Card title="Optimized Shunting Sequence">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th><th>Trainset</th><th>From</th><th>To</th>
                <th>Distance</th><th>Duration</th><th>Conflict</th>
              </tr>
            </thead>
            <tbody>
              {simResult.shunt_moves.slice(0, 8).map((move: any, i: number) => (
                <tr key={i}>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{i + 1}</td>
                  <td><span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{String(move.trainset)}</span></td>
                  <td><span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-1)' }}>{String(move.from)}</span></td>
                  <td><span style={{ fontFamily: 'var(--font-mono)', color: '#10b981' }}>{String(move.to)}</span></td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{Number(move.distance_m).toFixed(0)}m</td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{Number(move.duration_mins).toFixed(1)} min</td>
                  <td>
                    {move.has_conflict
                      ? <span style={{ color: '#ef4444', fontSize: 10 }}>⚠ Conflict</span>
                      : <span style={{ color: '#10b981', fontSize: 10 }}>✓ Clear</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
