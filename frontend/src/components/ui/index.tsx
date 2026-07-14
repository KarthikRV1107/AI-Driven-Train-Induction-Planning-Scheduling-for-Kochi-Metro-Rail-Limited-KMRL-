// ============================================================
// KMRL NexusAI — Core UI Components
// ============================================================
'use client'

import React from 'react'
import { TrainsetStatus } from '@/lib/api'

// ── Status Helpers ────────────────────────────────────────────────────────

export const STATUS_META: Record<TrainsetStatus, { label: string; color: string; bg: string }> = {
  revenue_service: { label: 'Revenue', color: '#10b981', bg: 'rgba(16,185,129,.12)' },
  standby:         { label: 'Standby', color: '#f59e0b', bg: 'rgba(245,158,11,.12)' },
  ibl:             { label: 'IBL',     color: '#8b5cf6', bg: 'rgba(139,92,246,.12)' },
  maintenance:     { label: 'Maint.',  color: '#ef4444', bg: 'rgba(239,68,68,.12)'  },
  cleaning:        { label: 'Clean',   color: '#3b82f6', bg: 'rgba(59,130,246,.12)' },
  stabling:        { label: 'Stabled', color: '#64748b', bg: 'rgba(100,116,139,.12)'},
  out_of_service:  { label: 'OOS',     color: '#ef4444', bg: 'rgba(239,68,68,.08)'  },
}

export function StatusBadge({
  status,
  ...props
}: { status: TrainsetStatus } & React.HTMLAttributes<HTMLSpanElement>) {
  const meta = STATUS_META[status] ?? STATUS_META.stabling
  return (
    <span
      {...props}
      style={{
        background: meta.bg,
        color: meta.color,
        fontSize: 10,
        fontWeight: 700,
        padding: '2px 7px',
        borderRadius: 4,
        letterSpacing: '.5px',
        textTransform: 'uppercase',
        display: 'inline-block',
        fontFamily: 'var(--font-sans)',
      }}
    >
      {meta.label}
    </span>
  )
}

// ── Severity Badge ─────────────────────────────────────────────────────────

const SEV_META = {
  critical: { color: '#ef4444', bg: 'rgba(239,68,68,.15)', border: 'rgba(239,68,68,.3)', icon: '●' },
  warning:  { color: '#f59e0b', bg: 'rgba(245,158,11,.15)', border: 'rgba(245,158,11,.3)', icon: '▲' },
  info:     { color: '#3b82f6', bg: 'rgba(59,130,246,.12)', border: 'rgba(59,130,246,.25)', icon: 'ℹ' },
}

export function SeverityBadge({
  severity,
  ...props
}: { severity: 'critical' | 'warning' | 'info' } & React.HTMLAttributes<HTMLSpanElement>) {
  const meta = SEV_META[severity]
  return (
    <span
      {...props}
      style={{
        background: meta.bg, color: meta.color,
        border: `1px solid ${meta.border}`,
        fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
        letterSpacing: '.5px', textTransform: 'uppercase',
        display: 'inline-flex', alignItems: 'center', gap: 4,
        ...(props.style ?? {}),
      }}
    >
      <span style={{ fontSize: 8 }}>{meta.icon}</span>
      {severity}
    </span>
  )
}

// ── KPI Tile ──────────────────────────────────────────────────────────────

interface KPITileProps {
  label: string
  value: string | number
  sub?: string
  delta?: { value: string; direction: 'up' | 'down' | 'neutral' }
  accent?: string
  sparkData?: number[]
}

export function KPITile({ label, value, sub, delta, accent = '#3b82f6', sparkData }: KPITileProps) {
  const deltaColor = delta?.direction === 'up' ? '#10b981' : delta?.direction === 'down' ? '#ef4444' : '#64748b'
  const deltaBg = delta?.direction === 'up' ? 'rgba(16,185,129,.1)' : delta?.direction === 'down' ? 'rgba(239,68,68,.1)' : 'rgba(100,116,139,.1)'

  return (
    <div style={{
      background: 'var(--bg-2)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '14px 16px', position: 'relative', overflow: 'hidden',
    }}>
      {/* Accent top border */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: accent, borderRadius: '8px 8px 0 0' }} />

      <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-2)', letterSpacing: '.7px', textTransform: 'uppercase', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: -1, lineHeight: 1, color: accent, fontFamily: 'var(--font-mono)' }}>
        {value}
      </div>
      <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
        {sub && <span style={{ fontSize: 11, color: 'var(--text-2)' }}>{sub}</span>}
        {delta && (
          <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 6px', borderRadius: 4, background: deltaBg, color: deltaColor }}>
            {delta.value}
          </span>
        )}
      </div>

      {/* Mini sparkline */}
      {sparkData && sparkData.length > 1 && (
        <MiniSparkline data={sparkData} color={accent} style={{ marginTop: 8 }} />
      )}
    </div>
  )
}

// ── Mini Sparkline ────────────────────────────────────────────────────────

function MiniSparkline({ data, color, style }: { data: number[]; color: string; style?: React.CSSProperties }) {
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const h = 28
  const w = 100
  const pts = data.map((v, i) => ({
    x: (i / (data.length - 1)) * w,
    y: h - ((v - min) / range) * h,
  }))
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')

  return (
    <div style={style}>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 28, overflow: 'visible' }}>
        <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity=".8" />
        <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r="2" fill={color} />
      </svg>
    </div>
  )
}

// ── Confidence Ring ───────────────────────────────────────────────────────

export function ConfidenceRing({
  value, size = 44, strokeWidth = 3,
}: { value: number; size?: number; strokeWidth?: number }) {
  const r = (size - strokeWidth * 2) / 2
  const circ = 2 * Math.PI * r
  const offset = circ - (value / 100) * circ
  const color = value >= 85 ? '#10b981' : value >= 65 ? '#f59e0b' : '#ef4444'

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg-3)" strokeWidth={strokeWidth} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset .5s ease' }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: size > 40 ? 10 : 8, fontWeight: 700, color, fontFamily: 'var(--font-mono)',
      }}>
        {value}%
      </div>
    </div>
  )
}

// ── Health Bar Row ────────────────────────────────────────────────────────

export function HealthBar({ label, value, width = 80 }: { label: string; value: number; width?: number }) {
  const color = value >= 80 ? '#10b981' : value >= 60 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
      <span style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.5px', width: 36, flexShrink: 0 }}>{label}</span>
      <div style={{ width, height: 3, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${value}%`, height: '100%', background: color, borderRadius: 2, transition: 'width .5s ease' }} />
      </div>
      <span style={{ fontSize: 9, color: 'var(--text-2)', fontFamily: 'var(--font-mono)', width: 28, textAlign: 'right' }}>{value}%</span>
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────

export function Skeleton({ width = '100%', height = 16, style }: { width?: number | string; height?: number; style?: React.CSSProperties }) {
  return (
    <div className="skeleton" style={{ width, height, borderRadius: 4, ...style }} />
  )
}

export function SkeletonCard() {
  return (
    <div style={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, padding: 12 }}>
      <Skeleton height={12} width="40%" style={{ marginBottom: 8 }} />
      <Skeleton height={28} width="60%" style={{ marginBottom: 10 }} />
      <Skeleton height={3} style={{ marginBottom: 4 }} />
      <Skeleton height={3} width="80%" style={{ marginBottom: 4 }} />
      <Skeleton height={3} width="60%" />
    </div>
  )
}

// ── Live Pulse ────────────────────────────────────────────────────────────

export function LivePulse({ color = '#10b981' }: { color?: string }) {
  return (
    <span style={{
      display: 'inline-block', width: 7, height: 7,
      background: color, borderRadius: '50%',
      boxShadow: `0 0 0 2px ${color}33`,
    }} className="pulse-dot" />
  )
}

// ── Section Header ────────────────────────────────────────────────────────

export function SectionHeader({
  title, subtitle, actions,
}: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
      <div>
        <h1 style={{ fontSize: 18, fontWeight: 700, letterSpacing: -.5, color: 'var(--text-0)' }}>{title}</h1>
        {subtitle && <p style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 3 }}>{subtitle}</p>}
      </div>
      {actions && <div style={{ display: 'flex', gap: 8 }}>{actions}</div>}
    </div>
  )
}

// ── Card Shell ────────────────────────────────────────────────────────────

export function Card({
  title, titleIcon, children, style, headerRight,
}: {
  title?: string
  titleIcon?: React.ReactNode
  children: React.ReactNode
  style?: React.CSSProperties
  headerRight?: React.ReactNode
}) {
  return (
    <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, ...style }}>
      {title && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, fontWeight: 600, color: 'var(--text-2)', letterSpacing: '.8px', textTransform: 'uppercase' }}>
            {titleIcon}
            {title}
          </div>
          {headerRight}
        </div>
      )}
      {children}
    </div>
  )
}

// ── Empty State ───────────────────────────────────────────────────────────

export function EmptyState({ icon = '⊘', title, description }: { icon?: string; title: string; description?: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-2)' }}>
      <div style={{ fontSize: 28, marginBottom: 8, opacity: .4 }}>{icon}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)', marginBottom: 4 }}>{title}</div>
      {description && <div style={{ fontSize: 11 }}>{description}</div>}
    </div>
  )
}

// ── Error State ───────────────────────────────────────────────────────────

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div style={{ textAlign: 'center', padding: '24px 16px', color: 'var(--red)' }}>
      <div style={{ fontSize: 20, marginBottom: 6 }}>⚠</div>
      <div style={{ fontSize: 12, marginBottom: onRetry ? 10 : 0 }}>{message}</div>
      {onRetry && (
        <button className="btn btn-outline" onClick={onRetry} style={{ fontSize: 11 }}>
          Retry
        </button>
      )}
    </div>
  )
}

// ── Tooltip Wrapper ───────────────────────────────────────────────────────

export function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  return <div data-tooltip={text}>{children}</div>
}
