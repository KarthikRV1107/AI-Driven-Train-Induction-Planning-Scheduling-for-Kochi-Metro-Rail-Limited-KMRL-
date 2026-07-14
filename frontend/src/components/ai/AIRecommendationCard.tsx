// ============================================================
// KMRL NexusAI — AI Recommendation Card
// ============================================================
'use client'

import React, { useState } from 'react'
import { PlanItem } from '@/lib/api'
import { ConfidenceRing } from '@/components/ui'

interface AIRecommendationCardProps {
  item: PlanItem
  rank?: number
  showDetails?: boolean
}

const PRIORITY_META = {
  high: { color: '#10b981', bg: 'rgba(16,185,129,.12)', border: 'rgba(16,185,129,.25)', stripe: '#10b981' },
  med:  { color: '#f59e0b', bg: 'rgba(245,158,11,.12)',  border: 'rgba(245,158,11,.25)',  stripe: '#f59e0b' },
  low:  { color: '#ef4444', bg: 'rgba(239,68,68,.12)',   border: 'rgba(239,68,68,.25)',   stripe: '#ef4444' },
}

export default function AIRecommendationCard({ item, rank, showDetails = false }: AIRecommendationCardProps) {
  const [expanded, setExpanded] = useState(showDetails)
  const score = item.reasoning?.soft_score ?? 0
  const priority = score >= 80 ? 'high' : score >= 60 ? 'med' : 'low'
  const meta = PRIORITY_META[priority]
  const hasViolations = item.constraint_violations?.length > 0
  const reasons: string[] = item.reasoning?.human_reasons ?? []
  const factors = item.reasoning?.factors ?? {}

  return (
    <div style={{
      background: 'var(--bg-2)',
      border: `1px solid var(--border)`,
      borderLeft: `3px solid ${meta.stripe}`,
      borderRadius: 8,
      marginBottom: 8,
      overflow: 'hidden',
      transition: 'all .15s ease',
    }}>
      {/* Header row */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 14px', cursor: 'pointer',
        }}
      >
        {rank !== undefined && (
          <div style={{
            width: 22, height: 22, borderRadius: '50%', background: 'var(--bg-3)',
            border: '1px solid var(--border-2)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, fontWeight: 700, color: 'var(--text-2)', flexShrink: 0,
          }}>
            {rank}
          </div>
        )}

        {/* Trainset code */}
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 14, color: 'var(--text-0)', minWidth: 52 }}>
          {item.trainset_code}
        </span>

        {/* Status badge */}
        <span style={{
          fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
          background: meta.bg, color: meta.color, border: `1px solid ${meta.border}`,
          textTransform: 'uppercase', letterSpacing: '.5px',
        }}>
          Revenue Service
        </span>

        {hasViolations && (
          <span style={{ fontSize: 10, color: '#ef4444', marginLeft: 4 }}>⚠ {item.constraint_violations.length} violations</span>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <ConfidenceRing value={item.confidence_pct} size={36} strokeWidth={3} />
          <span style={{
            fontSize: 16, color: 'var(--text-2)', transition: 'transform .15s',
            transform: expanded ? 'rotate(180deg)' : 'none', display: 'inline-block',
          }}>▾</span>
        </div>
      </div>

      {/* Expandable detail panel */}
      {expanded && (
        <div style={{ padding: '0 14px 14px', borderTop: '1px solid var(--border)' }}>

          {/* Reasons */}
          {reasons.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-2)', letterSpacing: '.7px', textTransform: 'uppercase', marginBottom: 6 }}>
                AI Reasoning
              </div>
              {reasons.map((r, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginBottom: 4 }}>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: meta.color, flexShrink: 0, marginTop: 5 }} />
                  <span style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.5 }}>{r}</span>
                </div>
              ))}
            </div>
          )}

          {/* SHAP factor bars */}
          {Object.keys(factors).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-2)', letterSpacing: '.7px', textTransform: 'uppercase', marginBottom: 8 }}>
                SHAP Feature Importance
              </div>
              {Object.entries(factors).map(([key, val]) => {
                const pct = Math.min(Math.abs((val / 25) * 100), 100)
                const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                return (
                  <div key={key} style={{ marginBottom: 5 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-2)', marginBottom: 2 }}>
                      <span>{label}</span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{val.toFixed(1)}</span>
                    </div>
                    <div style={{ height: 3, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: `${pct}%`, height: '100%', background: meta.color, borderRadius: 2, transition: 'width .4s ease' }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Violations */}
          {hasViolations && (
            <div style={{
              marginTop: 10, padding: '8px 10px',
              background: 'rgba(239,68,68,.06)', border: '1px solid rgba(239,68,68,.2)',
              borderRadius: 6,
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: '#ef4444', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '.5px' }}>
                Constraint Violations
              </div>
              {item.constraint_violations.map((v, i) => (
                <div key={i} style={{ fontSize: 10, color: '#ef4444', marginBottom: 2 }}>• {v}</div>
              ))}
            </div>
          )}

          {/* Score breakdown */}
          <div style={{
            marginTop: 10, display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 10px', background: 'var(--bg-1)', borderRadius: 6,
            border: '1px solid var(--border)',
          }}>
            <span style={{ fontSize: 10, color: 'var(--text-2)', flex: 1 }}>Optimizer Soft Score</span>
            <div style={{ flex: 2, height: 4, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                width: `${score}%`, height: '100%', borderRadius: 2,
                background: `linear-gradient(90deg, var(--blue), ${meta.color})`,
                transition: 'width .5s ease',
              }} />
            </div>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: meta.color }}>{score.toFixed(1)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
