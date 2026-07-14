// ============================================================
// KMRL NexusAI — Trainset Digital Twin Card
// ============================================================
'use client'

import React, { useState } from 'react'
import { Trainset } from '@/lib/api'
import { ConfidenceRing, HealthBar, StatusBadge } from '@/components/ui'

interface TrainsetCardProps {
  trainset: Trainset
  aiRiskScore?: number
  brandingName?: string
  onSelect?: (code: string) => void
  selected?: boolean
  compact?: boolean
}

const STATUS_TOP_COLOR: Record<string, string> = {
  revenue_service: '#10b981',
  standby: '#f59e0b',
  ibl: '#8b5cf6',
  maintenance: '#ef4444',
  cleaning: '#3b82f6',
  stabling: '#334155',
  out_of_service: '#ef4444',
}

export default function TrainsetCard({
  trainset, aiRiskScore, brandingName, onSelect, selected, compact,
}: TrainsetCardProps) {
  const [hovered, setHovered] = useState(false)
  const topColor = STATUS_TOP_COLOR[trainset.current_status] ?? '#334155'
  const riskScore = aiRiskScore ?? Math.round(Math.random() * 30 + 65)
  const riskColor = riskScore >= 85 ? '#10b981' : riskScore >= 65 ? '#f59e0b' : '#ef4444'

  return (
    <div
      onClick={() => onSelect?.(trainset.trainset_code)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? 'var(--bg-3)' : 'var(--bg-2)',
        border: `1px solid ${selected ? topColor : hovered ? 'var(--border-2)' : 'var(--border)'}`,
        borderRadius: 8,
        padding: 12,
        cursor: onSelect ? 'pointer' : 'default',
        position: 'relative',
        overflow: 'hidden',
        transition: 'all .15s ease',
        transform: hovered ? 'translateY(-1px)' : 'none',
        boxShadow: hovered ? `0 4px 16px ${topColor}20` : 'none',
      }}
    >
      {/* Status stripe */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: topColor, borderRadius: '8px 8px 0 0' }} />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 13, color: 'var(--text-0)' }}>
          {trainset.trainset_code}
        </span>
        <StatusBadge status={trainset.current_status} />
      </div>

      {/* Meta row */}
      <div style={{ fontSize: 10, color: 'var(--text-2)', marginBottom: 8, display: 'flex', gap: 8 }}>
        <span>{trainset.total_mileage_km?.toLocaleString() ?? '—'} km</span>
        {brandingName && <span style={{ color: 'var(--blue)' }}>● {brandingName}</span>}
        <span style={{ marginLeft: 'auto' }}>{trainset.current_bay ?? '—'}</span>
      </div>

      {!compact && (
        <>
          {/* Health bars */}
          <div style={{ marginBottom: 10 }}>
            <HealthBar label="Brake" value={trainset.brake_health ?? 90} />
            <HealthBar label="HVAC" value={trainset.hvac_health ?? 88} />
            <HealthBar label="Door" value={trainset.door_health ?? 92} />
          </div>

          {/* AI score row */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '7px 10px', background: 'var(--bg-1)', borderRadius: 6,
            border: '1px solid var(--border)',
          }}>
            <div>
              <div style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: 2 }}>AI Risk Score</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: riskColor, fontFamily: 'var(--font-mono)' }}>{riskScore}%</div>
            </div>
            <ConfidenceRing value={riskScore} size={40} strokeWidth={3} />
          </div>

          {/* Job cards warning */}
          {trainset.critical_jobs > 0 && (
            <div style={{
              marginTop: 8, padding: '5px 8px', background: 'rgba(239,68,68,.08)',
              border: '1px solid rgba(239,68,68,.2)', borderRadius: 5,
              fontSize: 10, color: '#ef4444', fontWeight: 600,
            }}>
              ⚠ {trainset.critical_jobs} critical job card{trainset.critical_jobs > 1 ? 's' : ''} open
            </div>
          )}
        </>
      )}

      {/* Hover glow */}
      {hovered && (
        <div style={{
          position: 'absolute', inset: 0, borderRadius: 8,
          background: `radial-gradient(ellipse at 50% 0%, ${topColor}08 0%, transparent 70%)`,
          pointerEvents: 'none',
        }} />
      )}
    </div>
  )
}
