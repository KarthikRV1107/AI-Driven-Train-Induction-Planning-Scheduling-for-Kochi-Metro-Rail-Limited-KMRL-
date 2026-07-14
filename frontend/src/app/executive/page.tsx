// ============================================================
// KMRL NexusAI — Executive Dashboard Page
// Board-level KPIs, AI Trust Metrics, Governance Status
// ============================================================
'use client'

import React, { useState } from 'react'
import { Card, KPITile, SectionHeader, SeverityBadge } from '@/components/ui'

// ── Demo data matching executive_reporting.py output ──────────────────────

const KPI_IMPROVEMENTS = [
  { metric: 'Fleet Availability',       baseline: 87.2,  current: 92.4,  pct: 6.0,  unit: '%',     better: true  },
  { metric: 'Shunting Operations',       baseline: 22.4,  current: 13.8,  pct: 38.4, unit: 'ops',   better: true  },
  { metric: 'Branding SLA Compliance',   baseline: 81.3,  current: 97.1,  pct: 19.4, unit: '%',     better: true  },
  { metric: 'Planning Time',             baseline: 47.0,  current: 0.5,   pct: 98.9, unit: 'min',   better: true  },
  { metric: 'Mileage Std Deviation',     baseline: 28.6,  current: 12.4,  pct: 56.6, unit: 'km',    better: true  },
  { metric: 'Maintenance Delays/Month',  baseline: 6.8,   current: 2.1,   pct: 69.1, unit: 'events',better: true  },
  { metric: 'Plan Override Rate',        baseline: 35.2,  current: 8.5,   pct: 75.9, unit: '%',     better: true  },
  { metric: 'Cert Alerts Missed',        baseline: 4.1,   current: 0.0,   pct: 100,  unit: 'alerts',better: true  },
  { metric: 'Cost Per Plan',             baseline: 12400, current: 1850,  pct: 85.1, unit: '₹',     better: true  },
]

const FINANCIAL_VALUE = {
  shunting:    2_67_910,
  availability: 21_33_750,
  planning:    1_12_867,
  maintenance: 67_68_000,
  total:       91_82_527,
  monthly:     7_65_211,
}

const SAFETY_RECORD = [
  { metric: 'Hard constraint violations',              target: 0, actual: 0 },
  { metric: 'Plans with expired certificates deployed', target: 0, actual: 0 },
  { metric: 'Plans with open critical jobs deployed',   target: 0, actual: 0 },
  { metric: 'Emergency stop activations',               target: 0, actual: 0 },
]

const AI_TRUST = {
  total_recommendations: 4_521,
  accepted: 4_137,
  modified: 312,
  rejected: 72,
  acceptance_rate: 91.5,
  avg_confidence: 88.2,
  ai_was_right: 218,
  human_was_right: 134,
}

const COMPLIANCE = [
  { name: 'CERT-In Directions 2022',  status: 'compliant' },
  { name: 'ISO 27001:2022 Alignment', status: 'compliant' },
  { name: 'DPDPA 2023',               status: 'compliant' },
  { name: 'RDSO AI Guidelines',       status: 'compliant' },
]

const MODE_HISTORY = [
  { from: 'shadow',   to: 'advisory',   date: '2025-02-15', approver: 'Ops Manager' },
  { from: 'advisory', to: 'assisted',   date: '2025-04-01', approver: 'Ops Manager + Platform Lead' },
]

// ── Improvement Bar ───────────────────────────────────────────────────────

function ImprovementBar({ item }: { item: typeof KPI_IMPROVEMENTS[0] }) {
  const color = item.better ? '#10b981' : '#ef4444'
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: 'var(--text-1)' }}>{item.metric}</span>
        <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
          {item.baseline}{item.unit} → <span style={{ color, fontWeight: 700 }}>{item.current}{item.unit}</span>
        </span>
      </div>
      <div style={{ height: 6, background: 'var(--bg-3)', borderRadius: 3, overflow: 'hidden', position: 'relative' }}>
        <div style={{
          width: `${Math.min(item.pct, 100)}%`, height: '100%',
          background: `linear-gradient(90deg, ${color}80, ${color})`,
          borderRadius: 3, transition: 'width .6s ease',
        }} />
      </div>
      <div style={{ fontSize: 10, color, fontWeight: 700, marginTop: 2, textAlign: 'right' }}>
        {item.better ? '↑' : '↓'} {item.pct.toFixed(1)}% improvement
      </div>
    </div>
  )
}

// ── Mode Pipeline ─────────────────────────────────────────────────────────

function ModePipeline() {
  const stages = [
    { key: 'shadow',     label: 'Shadow',     desc: 'Parallel validation' },
    { key: 'advisory',   label: 'Advisory',   desc: 'AI suggests only' },
    { key: 'assisted',   label: 'Assisted',   desc: 'Per-item approval' },
    { key: 'autonomous', label: 'Autonomous', desc: 'Supervised execution' },
  ]
  const currentIdx = 2 // assisted

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
      {stages.map((s, i) => {
        const isPast    = i < currentIdx
        const isCurrent = i === currentIdx
        const color = isCurrent ? '#3b82f6' : isPast ? '#10b981' : 'var(--text-3)'
        return (
          <React.Fragment key={s.key}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
              <div style={{
                width: 36, height: 36, borderRadius: '50%',
                background: isCurrent ? 'rgba(59,130,246,.15)' : isPast ? 'rgba(16,185,129,.1)' : 'var(--bg-3)',
                border: `2px solid ${color}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 14, fontWeight: 700, color,
                boxShadow: isCurrent ? '0 0 0 4px rgba(59,130,246,.1)' : 'none',
              }}>
                {isPast ? '✓' : i + 1}
              </div>
              <div style={{ fontSize: 11, fontWeight: 700, color: isCurrent ? color : 'var(--text-1)', marginTop: 6 }}>{s.label}</div>
              <div style={{ fontSize: 9, color: 'var(--text-2)', textAlign: 'center' }}>{s.desc}</div>
            </div>
            {i < stages.length - 1 && (
              <div style={{ flex: 0.5, height: 2, background: i < currentIdx ? '#10b981' : 'var(--border)', marginBottom: 28 }} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function ExecutiveDashboardPage() {
  const [activeTab, setActiveTab] = useState<'kpi' | 'trust' | 'governance'>('kpi')

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, animation: 'fade-up .25s ease' }}>
      <SectionHeader
        title="Executive Dashboard"
        subtitle="Board-level KPIs · AI Trust Report · Governance Status"
        actions={
          <>
            <span style={{
              fontSize: 11, fontFamily: 'var(--font-mono)', color: '#10b981',
              background: 'rgba(16,185,129,.1)', border: '1px solid rgba(16,185,129,.2)',
              padding: '5px 12px', borderRadius: 20,
            }}>
              ● Mode: ASSISTED
            </span>
            <button className="btn btn-outline">Export Board Report</button>
          </>
        }
      />

      {/* Top KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        <KPITile
          label="Annual Value Generated"
          value={`₹${(FINANCIAL_VALUE.total / 100000).toFixed(1)}L`}
          sub={`₹${(FINANCIAL_VALUE.monthly / 100000).toFixed(1)}L / month`}
          accent="#10b981"
          delta={{ value: 'vs pre-AI baseline', direction: 'up' }}
        />
        <KPITile
          label="Safety Violations (YTD)"
          value="0"
          sub="100% hard constraint compliance"
          accent="#3b82f6"
          delta={{ value: 'Perfect record', direction: 'up' }}
        />
        <KPITile
          label="AI Acceptance Rate"
          value={`${AI_TRUST.acceptance_rate}%`}
          sub={`${AI_TRUST.total_recommendations.toLocaleString()} recommendations`}
          accent="#8b5cf6"
          delta={{ value: 'Target >90%', direction: 'up' }}
        />
        <KPITile
          label="Compliance Status"
          value="4/4"
          sub="frameworks compliant"
          accent="#10b981"
          delta={{ value: 'All current', direction: 'up' }}
        />
      </div>

      {/* Tabs */}
      <Card>
        <div style={{ display: 'flex', gap: 2, marginBottom: 14 }}>
          {([
            ['kpi', '⬡ KPI Improvement vs Baseline'],
            ['trust', '◈ AI Trust & Decision Quality'],
            ['governance', '⊞ Governance & Mode Status'],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              style={{
                padding: '5px 14px', borderRadius: 6, cursor: 'pointer',
                fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-sans)', border: 'none',
                background: activeTab === key ? 'var(--bg-4)' : 'transparent',
                color: activeTab === key ? 'var(--blue)' : 'var(--text-2)',
                borderBottom: activeTab === key ? '1px solid var(--blue)' : '1px solid transparent',
                transition: 'all .15s',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {activeTab === 'kpi' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 12 }}>
                Measured improvement vs documented pre-AI manual planning baseline (87.2% availability era).
                Source: <span style={{ fontFamily: 'var(--font-mono)' }}>governance/executive_reporting.py</span>
              </div>
              {KPI_IMPROVEMENTS.map(item => <ImprovementBar key={item.metric} item={item} />)}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px' }}>
                Financial Value Breakdown (Annual)
              </div>
              {[
                ['Shunting reduction', FINANCIAL_VALUE.shunting],
                ['Availability revenue gain', FINANCIAL_VALUE.availability],
                ['Planning efficiency', FINANCIAL_VALUE.planning],
                ['Maintenance delay avoidance', FINANCIAL_VALUE.maintenance],
              ].map(([label, val]) => (
                <div key={label as string} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '9px 12px', background: 'var(--bg-2)', borderRadius: 6, border: '1px solid var(--border)',
                }}>
                  <span style={{ fontSize: 11, color: 'var(--text-1)' }}>{label}</span>
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#10b981' }}>
                    ₹{(Number(val) / 100000).toFixed(2)}L
                  </span>
                </div>
              ))}
              <div style={{
                marginTop: 4, padding: '12px', background: 'rgba(16,185,129,.06)',
                border: '1px solid rgba(16,185,129,.2)', borderRadius: 6,
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-0)' }}>Total Annual Value</span>
                <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#10b981' }}>
                  ₹{(FINANCIAL_VALUE.total / 100000).toFixed(1)}L
                </span>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'trust' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 10 }}>
                Decision Quality (Last Quarter)
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                {[
                  ['Total Recommendations', AI_TRUST.total_recommendations.toLocaleString(), '#3b82f6'],
                  ['Accepted As-Is', `${AI_TRUST.accepted.toLocaleString()} (${AI_TRUST.acceptance_rate}%)`, '#10b981'],
                  ['Modified by Operator', AI_TRUST.modified.toLocaleString(), '#f59e0b'],
                  ['Rejected Outright', AI_TRUST.rejected.toLocaleString(), '#ef4444'],
                ].map(([label, val, color]) => (
                  <div key={label as string} style={{ padding: '10px 12px', background: 'var(--bg-2)', borderRadius: 6, border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: 3 }}>{label}</div>
                    <div style={{ fontSize: 16, fontFamily: 'var(--font-mono)', fontWeight: 700, color: color as string }}>{val}</div>
                  </div>
                ))}
              </div>

              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 8 }}>
                Retrospective Override Validation
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ flex: 1, padding: '10px 12px', background: 'rgba(59,130,246,.06)', border: '1px solid rgba(59,130,246,.2)', borderRadius: 6 }}>
                  <div style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 3 }}>AI was retrospectively correct</div>
                  <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#3b82f6' }}>{AI_TRUST.ai_was_right}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-2)' }}>{(AI_TRUST.ai_was_right / (AI_TRUST.modified + AI_TRUST.rejected) * 100).toFixed(0)}% of overrides</div>
                </div>
                <div style={{ flex: 1, padding: '10px 12px', background: 'rgba(16,185,129,.06)', border: '1px solid rgba(16,185,129,.2)', borderRadius: 6 }}>
                  <div style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 3 }}>Human judgment was correct</div>
                  <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#10b981' }}>{AI_TRUST.human_was_right}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-2)' }}>{(AI_TRUST.human_was_right / (AI_TRUST.modified + AI_TRUST.rejected) * 100).toFixed(0)}% of overrides</div>
                </div>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 10 }}>
                Safety Record (Zero Tolerance)
              </div>
              {SAFETY_RECORD.map(s => (
                <div key={s.metric} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '9px 12px', marginBottom: 6, background: 'var(--bg-2)', borderRadius: 6, border: '1px solid var(--border)',
                }}>
                  <span style={{ fontSize: 11, color: 'var(--text-1)' }}>{s.metric}</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: s.actual === s.target ? '#10b981' : '#ef4444' }}>
                      {s.actual}
                    </span>
                    <span style={{
                      fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 3,
                      background: s.actual === s.target ? 'rgba(16,185,129,.1)' : 'rgba(239,68,68,.1)',
                      color: s.actual === s.target ? '#10b981' : '#ef4444',
                    }}>
                      {s.actual === s.target ? '✓ COMPLIANT' : '✕ VIOLATION'}
                    </span>
                  </span>
                </div>
              ))}

              <div style={{ marginTop: 14, fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 8 }}>
                Explainability Coverage
              </div>
              {[
                ['Recommendations with human-readable reasons', '100%'],
                ['Recommendations with SHAP feature importance', '100%'],
                ['Constraint violations explicitly listed', '100%'],
              ].map(([label, val]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-1)' }}>{label}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#10b981', fontWeight: 700 }}>{val}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'governance' && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 16 }}>
              Safe Rollout Pipeline
            </div>
            <div style={{ padding: '20px 10px 10px', marginBottom: 20 }}>
              <ModePipeline />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 8 }}>
                  Mode Transition History
                </div>
                {MODE_HISTORY.map((m, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
                    background: 'var(--bg-2)', borderRadius: 6, border: '1px solid var(--border)', marginBottom: 6,
                  }}>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>{m.date}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-1)' }}>{m.from} → <span style={{ color: '#3b82f6', fontWeight: 700 }}>{m.to}</span></span>
                    <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-2)' }}>{m.approver}</span>
                  </div>
                ))}
                <div style={{ marginTop: 10, padding: '10px 12px', background: 'rgba(59,130,246,.06)', border: '1px solid rgba(59,130,246,.2)', borderRadius: 6, fontSize: 11, color: 'var(--text-1)' }}>
                  <strong style={{ color: '#3b82f6' }}>Promotion to Autonomous</strong> requires: 90-day Assisted period (currently 71 days), agreement rate ≥90% sustained, Ops Manager + Platform Lead + CTO sign-off.
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 8 }}>
                  Compliance Frameworks
                </div>
                {COMPLIANCE.map(c => (
                  <div key={c.name} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '9px 12px', marginBottom: 6, background: 'var(--bg-2)', borderRadius: 6, border: '1px solid var(--border)',
                  }}>
                    <span style={{ fontSize: 11, color: 'var(--text-1)' }}>{c.name}</span>
                    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 3, background: 'rgba(16,185,129,.1)', color: '#10b981' }}>
                      ✓ Compliant
                    </span>
                  </div>
                ))}

                <div style={{ marginTop: 14, fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 8 }}>
                  Emergency Controls
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <div style={{ flex: 1, padding: '10px 12px', background: 'var(--bg-2)', borderRadius: 6, border: '1px solid var(--border)', textAlign: 'center' }}>
                    <div style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 4 }}>Emergency Stop</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#10b981' }}>● READY</div>
                  </div>
                  <div style={{ flex: 1, padding: '10px 12px', background: 'var(--bg-2)', borderRadius: 6, border: '1px solid var(--border)', textAlign: 'center' }}>
                    <div style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 4 }}>Pending Approvals</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-0)', fontFamily: 'var(--font-mono)' }}>0</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
