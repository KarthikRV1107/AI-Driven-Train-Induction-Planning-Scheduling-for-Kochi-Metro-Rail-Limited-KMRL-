// ============================================================
// KMRL NexusAI — Alerts & Incidents Page
// ============================================================
'use client'

import React, { useState } from 'react'
import { useAlerts } from '@/hooks'
import { Alert, AlertSeverity } from '@/lib/api'
import {
  Card, EmptyState, SectionHeader,
  SeverityBadge, Skeleton,
} from '@/components/ui'

// ── Alert Item ────────────────────────────────────────────────────────────

function AlertItem({
  alert, onAck,
}: { alert: Alert; onAck: (id: string) => void }) {
  const [acking, setAcking] = useState(false)

  const handleAck = async () => {
    setAcking(true)
    await onAck(alert.id)
    setAcking(false)
  }

  const timeStr = new Date(alert.created_at).toLocaleTimeString('en-IN', {
    hour12: false, timeZone: 'Asia/Kolkata',
  })
  const dateStr = new Date(alert.created_at).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', timeZone: 'Asia/Kolkata',
  })

  const ICONS: Record<AlertSeverity, string> = {
    critical: '🚨', warning: '⚠️', info: 'ℹ️',
  }

  const BG: Record<AlertSeverity, string> = {
    critical: 'rgba(239,68,68,.06)',
    warning:  'rgba(245,158,11,.04)',
    info:     'transparent',
  }

  const BORDER: Record<AlertSeverity, string> = {
    critical: 'rgba(239,68,68,.2)',
    warning:  'rgba(245,158,11,.15)',
    info:     'var(--border)',
  }

  return (
    <div
      data-cy="alert-item"
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 12,
        padding: '13px 14px',
        background: alert.is_acknowledged ? 'transparent' : BG[alert.severity],
        border: `1px solid ${alert.is_acknowledged ? 'var(--border)' : BORDER[alert.severity]}`,
        borderRadius: 8, marginBottom: 6,
        opacity: alert.is_acknowledged ? .55 : 1,
        transition: 'all .15s',
      }}
    >
      {/* Icon */}
      <div style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }}>{ICONS[alert.severity]}</div>

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-0)' }}>
            {alert.title}
          </span>
          <SeverityBadge severity={alert.severity} data-cy="severity-badge" />
          {alert.is_acknowledged && (
            <span style={{ fontSize: 10, color: '#10b981', marginLeft: 'auto', flexShrink: 0 }}>✓ Acknowledged</span>
          )}
        </div>

        {alert.description && (
          <p style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.5, marginBottom: 5 }}>
            {alert.description}
          </p>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 10, color: 'var(--text-2)' }}>
          <span style={{ fontFamily: 'var(--font-mono)' }}>{dateStr} · {timeStr} IST</span>
          {alert.trainset_code && (
            <>
              <span>·</span>
              <span style={{
                background: 'var(--bg-3)', padding: '1px 6px', borderRadius: 3,
                fontFamily: 'var(--font-mono)', color: 'var(--text-1)',
              }}>
                {alert.trainset_code}
              </span>
            </>
          )}
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>{alert.alert_code}</span>
        </div>
      </div>

      {/* Actions */}
      {!alert.is_acknowledged && (
        <button
          data-cy="ack-btn"
          className="btn btn-outline"
          onClick={handleAck}
          disabled={acking}
          style={{ fontSize: 10, padding: '3px 10px', flexShrink: 0, marginTop: 2 }}
        >
          {acking ? '…' : 'Acknowledge'}
        </button>
      )}
    </div>
  )
}

// ── Stats row ────────────────────────────────────────────────────────────

function AlertStats({ alerts }: { alerts: Alert[] }) {
  const critical  = alerts.filter(a => a.severity === 'critical' && !a.is_acknowledged).length
  const warning   = alerts.filter(a => a.severity === 'warning'  && !a.is_acknowledged).length
  const info      = alerts.filter(a => a.severity === 'info'     && !a.is_acknowledged).length
  const acked     = alerts.filter(a => a.is_acknowledged).length

  const stats = [
    { label: 'Critical',      value: critical, color: '#ef4444', bg: 'rgba(239,68,68,.1)'  },
    { label: 'Warning',       value: warning,  color: '#f59e0b', bg: 'rgba(245,158,11,.1)' },
    { label: 'Info',          value: info,     color: '#3b82f6', bg: 'rgba(59,130,246,.1)' },
    { label: 'Acknowledged',  value: acked,    color: '#10b981', bg: 'rgba(16,185,129,.1)' },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
      {stats.map(s => (
        <div key={s.label} style={{
          padding: '12px 14px', background: s.bg,
          border: `1px solid ${s.color}30`, borderRadius: 8,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{ fontSize: 24, fontWeight: 700, fontFamily: 'var(--font-mono)', color: s.color }}>
            {s.value}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-1)' }}>{s.label}</span>
        </div>
      ))}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function AlertsPage() {
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | undefined>()
  const [showAcked, setShowAcked] = useState(false)

  const { alerts, loading, error, criticalCount, acknowledge, refetch } = useAlerts(
    severityFilter, showAcked ? undefined : false,
  )

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, animation: 'fade-up .25s ease' }}>
      <SectionHeader
        title="Alerts & Incidents"
        subtitle={`${alerts.length} active · ${criticalCount} critical · Auto-monitored by AI`}
        actions={
          <>
            <button className="btn btn-outline" onClick={refetch}>↻ Refresh</button>
            <button className="btn btn-outline" onClick={() => alerts.filter(a => !a.is_acknowledged).forEach(a => acknowledge(a.id))}>
              ✓ Mark All Read
            </button>
            <button className="btn btn-primary">Configure Alerts</button>
          </>
        }
      />

      {/* Stats */}
      <AlertStats alerts={alerts} />

      {/* Filter bar */}
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: 'var(--text-2)', fontWeight: 600, marginRight: 4 }}>Filter:</span>

          {[
            { label: 'All',      value: undefined         },
            { label: '🔴 Critical', value: 'critical' as AlertSeverity },
            { label: '🟡 Warning',  value: 'warning'  as AlertSeverity },
            { label: 'ℹ Info',     value: 'info'     as AlertSeverity },
          ].map(f => (
            <button
              data-cy="severity-filter"
              key={f.label}
              onClick={() => setSeverityFilter(f.value)}
              style={{
                padding: '4px 12px', borderRadius: 5, fontSize: 11,
                fontWeight: 500, cursor: 'pointer', fontFamily: 'var(--font-sans)',
                border: 'none',
                background: severityFilter === f.value ? 'var(--bg-4)' : 'transparent',
                color: severityFilter === f.value ? 'var(--text-0)' : 'var(--text-2)',
                borderBottom: severityFilter === f.value ? '1px solid var(--blue)' : '1px solid transparent',
                transition: 'all .12s',
              }}
            >
              {f.label}
            </button>
          ))}

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 11, color: 'var(--text-1)' }}>
              <input
                type="checkbox"
                checked={showAcked}
                onChange={e => setShowAcked(e.target.checked)}
                style={{ accentColor: 'var(--blue)' }}
              />
              Show acknowledged
            </label>

            <select className="select" style={{ width: 140 }}>
              <option>Newest first</option>
              <option>Oldest first</option>
              <option>Severity</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Alert list */}
      <div>
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} height={80} style={{ marginBottom: 6 }} />)
        ) : error ? (
          <div style={{ padding: 20, color: '#ef4444', fontSize: 12, textAlign: 'center' }}>
            {error}
          </div>
        ) : alerts.length === 0 ? (
          <EmptyState icon="✓" title="No alerts" description="All systems nominal" />
        ) : (
          alerts.map(alert => (
            <AlertItem key={alert.id} alert={alert} onAck={acknowledge} />
          ))
        )}
      </div>

      {/* Alert rules summary */}
      <Card title="Active Alert Rules" headerRight={
        <button className="btn btn-outline" style={{ fontSize: 10, padding: '3px 10px' }}>Edit Rules</button>
      }>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          {[
            { rule: 'Fitness cert expiry < 7 days',       channel: 'Email + SMS',      active: true  },
            { rule: 'AI failure risk > 70%',               channel: 'Dashboard + Email', active: true  },
            { rule: 'Bay conflict detected',               channel: 'Dashboard',         active: true  },
            { rule: 'Critical job card open > 24h',        channel: 'Email + WhatsApp',  active: true  },
            { rule: 'Branding SLA compliance < 90%',       channel: 'Email',             active: true  },
            { rule: 'Mileage deviation > 30km avg',        channel: 'Dashboard',         active: false },
            { rule: 'Telemetry anomaly detected',          channel: 'Dashboard',         active: true  },
            { rule: 'Maintenance overrun > 2h',            channel: 'SMS + Email',       active: true  },
          ].map(r => (
            <div key={r.rule} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px',
              background: 'var(--bg-2)', borderRadius: 6, border: '1px solid var(--border)',
            }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                background: r.active ? '#10b981' : '#334155',
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, color: 'var(--text-0)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.rule}</div>
                <div style={{ fontSize: 9, color: 'var(--text-2)' }}>{r.channel}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
