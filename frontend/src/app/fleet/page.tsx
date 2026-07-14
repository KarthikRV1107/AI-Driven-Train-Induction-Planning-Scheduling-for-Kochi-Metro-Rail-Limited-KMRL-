// ============================================================
// KMRL NexusAI — Fleet Status Page
// 25 trainsets · Digital twin cards · Live health feed
// ============================================================
'use client'

import React, { useMemo, useState } from 'react'
import { useFleet, useWebSocket } from '@/hooks'
import { fleetApi, Trainset, TrainsetStatus } from '@/lib/api'
import TrainsetCard from '@/components/fleet/TrainsetCard'
import {
  Card, ConfidenceRing, EmptyState, ErrorState,
  HealthBar, KPITile, SectionHeader, SeverityBadge,
  SkeletonCard, StatusBadge, Tooltip,
} from '@/components/ui'

// ── Status filter tabs ────────────────────────────────────────────────────

const FILTER_TABS: { value: TrainsetStatus | 'all'; label: string; color: string }[] = [
  { value: 'all',             label: 'All (25)',    color: '#94a3b8' },
  { value: 'revenue_service', label: 'Revenue (18)', color: '#10b981' },
  { value: 'standby',        label: 'Standby (3)',  color: '#f59e0b' },
  { value: 'ibl',            label: 'IBL (2)',      color: '#8b5cf6' },
  { value: 'maintenance',    label: 'Maint. (2)',   color: '#ef4444' },
]

// ── Trainset Detail Drawer ────────────────────────────────────────────────

function TrainsetDrawer({
  trainset, onClose,
}: { trainset: Trainset; onClose: () => void }) {
  const [overriding, setOverriding] = useState(false)
  const [newStatus, setNewStatus]   = useState<TrainsetStatus>(trainset.current_status)
  const [saving, setSaving]         = useState(false)
  const [saved, setSaved]           = useState(false)
  const aiScore = Math.round(
    (trainset.brake_health + trainset.hvac_health + trainset.door_health) / 3
  )

  const handleSave = async () => {
    setSaving(true)
    try {
      await fleetApi.updateStatus(trainset.trainset_code, newStatus)
      setSaved(true)
      setTimeout(() => { setSaved(false); setOverriding(false) }, 1500)
    } finally {
      setSaving(false)
    }
  }

  const CERT_ROWS = [
    { name: 'Rolling Stock Fitness', days: 42, ok: true  },
    { name: 'Signalling Clearance',  days: 18, ok: true  },
    { name: 'Telecom Clearance',     days: 7,  ok: false },
    { name: 'Brake Health Cert',     days: 31, ok: true  },
    { name: 'HVAC Certificate',      days: 12, ok: true  },
    { name: 'Door System Cert',      days: 55, ok: true  },
  ]

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: 380,
      background: 'var(--bg-1)', borderLeft: '1px solid var(--border)',
      zIndex: 200, display: 'flex', flexDirection: 'column',
      animation: 'fade-in .15s ease',
      boxShadow: '-8px 0 32px rgba(0,0,0,.4)',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 18px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10, background: 'var(--bg-2)',
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 18 }}>
              {trainset.trainset_code}
            </span>
            <StatusBadge status={trainset.current_status} />
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-2)' }}>
            {trainset.rake_number} · Bay {trainset.current_bay ?? '—'} · 4-car rake
          </div>
        </div>
        <ConfidenceRing value={aiScore} size={50} strokeWidth={4} />
        <button onClick={onClose} style={{
          width: 28, height: 28, borderRadius: 6, border: '1px solid var(--border)',
          background: 'var(--bg-3)', cursor: 'pointer', color: 'var(--text-1)',
          fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>×</button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* System health */}
        <div style={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.7px', marginBottom: 10 }}>
            System Health
          </div>
          <HealthBar label="Brake" value={trainset.brake_health ?? 90} width={140} />
          <HealthBar label="HVAC"  value={trainset.hvac_health  ?? 88} width={140} />
          <HealthBar label="Door"  value={trainset.door_health  ?? 92} width={140} />
        </div>

        {/* Quick stats */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {[
            { label: 'Total Mileage',    value: `${(trainset.total_mileage_km ?? 0).toLocaleString()} km` },
            { label: 'Current Bay',      value: trainset.current_bay ?? '—'                                },
            { label: 'Days Since Svc',   value: `${trainset.days_since_service ?? 0}d`                     },
            { label: 'Days Since IBL',   value: `${trainset.days_since_ibl ?? 0}d`                         },
            { label: 'Open Job Cards',   value: `${trainset.open_jobs ?? 0}`                                },
            { label: 'Critical Jobs',    value: `${trainset.critical_jobs ?? 0}` },
          ].map(s => (
            <div key={s.label} style={{
              padding: '8px 10px', background: 'var(--bg-2)', borderRadius: 6,
              border: '1px solid var(--border)',
            }}>
              <div style={{ fontSize: 9, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.5px', marginBottom: 2 }}>{s.label}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--text-0)' }}>{s.value}</div>
            </div>
          ))}
        </div>

        {/* Certificates */}
        <div style={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.7px', marginBottom: 8 }}>
            Fitness Certificates
          </div>
          {CERT_ROWS.map(c => (
            <div key={c.name} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '5px 0', borderBottom: '1px solid rgba(30,45,64,.4)',
            }}>
              <span style={{ flex: 1, fontSize: 11, color: 'var(--text-1)' }}>{c.name}</span>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: c.days <= 7 ? '#f59e0b' : 'var(--text-2)' }}>{c.days}d</span>
              <span style={{
                fontSize: 9, padding: '1px 6px', borderRadius: 3, fontWeight: 600,
                background: c.ok ? 'rgba(16,185,129,.1)' : 'rgba(245,158,11,.1)',
                color: c.ok ? '#10b981' : '#f59e0b',
              }}>
                {c.ok ? 'Valid' : 'Expiring'}
              </span>
            </div>
          ))}
        </div>

        {/* Status override */}
        <div style={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: overriding ? 10 : 0 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.7px' }}>
              Manual Status Override
            </div>
            <button
              className="btn btn-outline"
              style={{ fontSize: 10, padding: '3px 10px' }}
              onClick={() => setOverriding(v => !v)}
            >
              {overriding ? 'Cancel' : 'Override'}
            </button>
          </div>

          {overriding && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <select className="select" value={newStatus} onChange={e => setNewStatus(e.target.value as TrainsetStatus)}>
                <option value="revenue_service">Revenue Service</option>
                <option value="standby">Standby</option>
                <option value="ibl">IBL</option>
                <option value="maintenance">Maintenance</option>
                <option value="cleaning">Cleaning</option>
                <option value="stabling">Stabling</option>
                <option value="out_of_service">Out of Service</option>
              </select>
              <button
                className="btn btn-primary"
                onClick={handleSave}
                disabled={saving}
                style={{ width: '100%', justifyContent: 'center', fontSize: 11 }}
              >
                {saving ? '⟳ Saving…' : saved ? '✓ Saved' : 'Apply Override'}
              </button>
              <div style={{ fontSize: 10, color: '#f59e0b' }}>
                ⚠ Manual overrides are audit-logged and reviewed by Operations Manager.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function FleetPage() {
  const [filterStatus, setFilterStatus] = useState<TrainsetStatus | 'all'>('all')
  const [search, setSearch]             = useState('')
  const [selected, setSelected]         = useState<Trainset | null>(null)
  const [sortBy, setSortBy]             = useState<'code' | 'mileage' | 'risk'>('code')

  const { data: fleet, loading, error, refetch } = useFleet(
    filterStatus !== 'all' ? filterStatus : undefined
  )
  const { latestStatusUpdates } = useWebSocket()

  // Merge real-time WS status updates
  const enrichedFleet = useMemo(() => {
    if (!fleet) return []
    return fleet.map(ts => ({
      ...ts,
      current_status: (latestStatusUpdates[ts.trainset_code] as TrainsetStatus) ?? ts.current_status,
    }))
  }, [fleet, latestStatusUpdates])

  // Filter + sort
  const filtered = useMemo(() => {
    let list = enrichedFleet
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(ts =>
        ts.trainset_code.toLowerCase().includes(q) ||
        ts.rake_number.toLowerCase().includes(q) ||
        (ts.current_bay ?? '').toLowerCase().includes(q)
      )
    }
    return [...list].sort((a, b) => {
      if (sortBy === 'mileage') return (b.total_mileage_km ?? 0) - (a.total_mileage_km ?? 0)
      if (sortBy === 'risk')    return (b.critical_jobs ?? 0) - (a.critical_jobs ?? 0)
      return a.trainset_code.localeCompare(b.trainset_code)
    })
  }, [enrichedFleet, search, sortBy])

  const counts = useMemo(() => ({
    revenue:     enrichedFleet.filter(t => t.current_status === 'revenue_service').length,
    standby:     enrichedFleet.filter(t => t.current_status === 'standby').length,
    ibl:         enrichedFleet.filter(t => t.current_status === 'ibl').length,
    maintenance: enrichedFleet.filter(t => t.current_status === 'maintenance').length,
  }), [enrichedFleet])

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, animation: 'fade-up .25s ease' }}>
      <SectionHeader
        title="Fleet Status"
        subtitle="25 trainsets · 4-car rake · Live telemetry · Muttom Depot"
        actions={
          <>
            <button className="btn btn-outline" onClick={refetch}>↻ Refresh</button>
            <button className="btn btn-outline">Export</button>
          </>
        }
      />

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        <KPITile label="Revenue Service" value={counts.revenue}     accent="#10b981" sub="in service tonight" />
        <KPITile label="Standby"         value={counts.standby}     accent="#f59e0b" sub="ready in 20 min"    />
        <KPITile label="IBL"             value={counts.ibl}         accent="#8b5cf6" sub="under inspection"   />
        <KPITile label="Maintenance"     value={counts.maintenance} accent="#ef4444" sub="workshop bay"       />
      </div>

      {/* Filter + search bar */}
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          {/* Status filter tabs */}
          <div style={{ display: 'flex', gap: 2 }}>
            {FILTER_TABS.map(tab => (
              <button
                key={tab.value}
                onClick={() => setFilterStatus(tab.value)}
                style={{
                  padding: '4px 12px', borderRadius: 5, cursor: 'pointer',
                  fontSize: 11, fontWeight: 500, fontFamily: 'var(--font-sans)',
                  border: 'none',
                  background: filterStatus === tab.value ? 'var(--bg-4)' : 'transparent',
                  color: filterStatus === tab.value ? tab.color : 'var(--text-2)',
                  borderBottom: filterStatus === tab.value ? `1px solid ${tab.color}` : '1px solid transparent',
                  transition: 'all .12s',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <input
            className="input"
            placeholder="Search trainset, rake no., bay…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: 220 }}
          />

          {/* Sort */}
          <select
            className="select"
            value={sortBy}
            onChange={e => setSortBy(e.target.value as typeof sortBy)}
            style={{ width: 140, marginLeft: 'auto' }}
          >
            <option value="code">Sort: Code</option>
            <option value="mileage">Sort: Mileage ↓</option>
            <option value="risk">Sort: Risk ↓</option>
          </select>

          <span style={{ fontSize: 11, color: 'var(--text-2)' }}>
            {filtered.length} trainsets
          </span>
        </div>
      </Card>

      {/* Trainset grid */}
      {error ? (
        <ErrorState message={error} onRetry={refetch} />
      ) : loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}>
          {Array.from({ length: 12 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState icon="◈" title="No trainsets found" description="Try clearing the search or filter" />
      ) : (
        <div
          data-cy="fleet-grid"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}
        >
          {filtered.map(ts => (
            <div key={ts.id} data-cy="trainset-card">
              <TrainsetCard
                trainset={ts}
                selected={selected?.id === ts.id}
                onSelect={code => {
                  const found = filtered.find(t => t.trainset_code === code) ?? null
                  setSelected(prev => prev?.id === found?.id ? null : found)
                }}
              />
            </div>
          ))}
        </div>
      )}

      {/* Critical flags summary */}
      {!loading && (
        <Card title="Critical Status Flags">
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {enrichedFleet.filter(ts => ts.critical_jobs > 0).length > 0 ? (
              enrichedFleet
                .filter(ts => ts.critical_jobs > 0)
                .map(ts => (
                  <div
                    key={ts.id}
                    data-cy="critical-jobs-warning"
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '6px 12px', background: 'rgba(239,68,68,.08)',
                      border: '1px solid rgba(239,68,68,.2)', borderRadius: 6,
                    }}
                  >
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12 }}>{ts.trainset_code}</span>
                    <span style={{ fontSize: 10, color: '#ef4444' }}>{ts.critical_jobs} critical job{ts.critical_jobs > 1 ? 's' : ''}</span>
                  </div>
                ))
            ) : (
              <div style={{ fontSize: 11, color: '#10b981' }}>✓ No critical job card flags tonight</div>
            )}
          </div>
        </Card>
      )}

      {/* Detail drawer */}
      {selected && <TrainsetDrawer trainset={selected} onClose={() => setSelected(null)} />}

      {/* Overlay backdrop */}
      {selected && (
        <div
          onClick={() => setSelected(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,.4)',
            zIndex: 199, cursor: 'pointer',
          }}
        />
      )}
    </div>
  )
}
