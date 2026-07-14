'use client'

import React, { useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAlerts, useISTClock, useKeyboardShortcut, useWebSocket } from '@/hooks'
import { LivePulse } from '@/components/ui'

const ICONS = {
  dashboard: 'M1 1h6v6H1zM9 1h6v6H9zM1 9h6v6H1zM9 9h6v6H9z',
  fleet: 'M1 11h14M3 11V5l5-3 5 3v6M5 11V8h6v3',
  schedule: 'M1 3h14v10H1zM5 1v4M11 1v4M1 7h14',
  depot: 'M1 13h14M1 13V7l7-5 7 5v6M5.5 9h5v4h-5z',
  maintenance: 'M8 1a5 5 0 110 10A5 5 0 018 1zM8 4v4l2 2',
  analytics: 'M1 14L5 9l3 2 3-4 4 4',
  alerts: 'M8 1a5 5 0 015 5v3l1.5 2.5H1.5L3 9V6a5 5 0 015-5zM6.5 13.5a1.5 1.5 0 003 0',
  settings: 'M8 10a2 2 0 100-4 2 2 0 000 4zM8 1v2M8 13v2M1 8h2M13 8h2',
} as const

const PRIMARY_NAV = [
  { href: '/dashboard', label: 'Command' },
  { href: '/fleet', label: 'Fleet' },
  { href: '/scheduler', label: 'Scheduler' },
  { href: '/depot', label: 'Depot' },
  { href: '/maintenance', label: 'Maintenance' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/executive', label: 'Executive' },
]

const COMMAND_ITEMS = [
  { id: 'dashboard', label: 'Open Command Center', href: '/dashboard', shortcut: 'Ctrl+K' },
  { id: 'fleet', label: 'Go to Fleet Status', href: '/fleet', shortcut: 'Fleet' },
  { id: 'scheduler', label: 'Open AI Scheduler', href: '/scheduler', shortcut: 'Plan' },
  { id: 'depot', label: 'Open Depot Digital Twin', href: '/depot', shortcut: 'Depot' },
  { id: 'maintenance', label: 'View Maintenance Intelligence', href: '/maintenance', shortcut: 'Health' },
  { id: 'analytics', label: 'Open Analytics and KPIs', href: '/analytics', shortcut: 'KPIs' },
  { id: 'executive', label: 'Executive Dashboard', href: '/executive', shortcut: 'Board' },
  { id: 'settings', label: 'Open Settings', href: '/settings', shortcut: 'Prefs' },
]

function Icon({ d, size = 16 }: { d: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d={d} stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SidebarSection({ title }: { title: string }) {
  return (
    <div
      style={{
        fontSize: 10,
        fontWeight: 600,
        color: 'var(--text-3)',
        letterSpacing: '1.2px',
        textTransform: 'uppercase',
        padding: '12px 8px 6px',
        marginTop: 4,
      }}
    >
      {title}
    </div>
  )
}

function NavItem({
  href,
  icon,
  label,
  badge,
  badgeType = 'default',
}: {
  href: string
  icon: keyof typeof ICONS
  label: string
  badge?: string | number
  badgeType?: 'default' | 'warn' | 'ok' | 'critical'
}) {
  const pathname = usePathname()
  const active = pathname === href || pathname.startsWith(`${href}/`)
  const badgeColors = {
    default: { bg: 'var(--bg-3)', color: 'var(--text-1)' },
    warn: { bg: 'rgba(245,158,11,.15)', color: '#f59e0b' },
    ok: { bg: 'rgba(16,185,129,.15)', color: '#10b981' },
    critical: { bg: 'rgba(239,68,68,.15)', color: '#ef4444' },
  }
  const bc = badgeColors[badgeType]

  return (
    <Link href={href} style={{ textDecoration: 'none' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '7px 8px',
          borderRadius: 6,
          cursor: 'pointer',
          color: active ? 'var(--blue)' : 'var(--text-1)',
          background: active ? 'rgba(59,130,246,.08)' : 'transparent',
          border: active ? '1px solid rgba(59,130,246,.15)' : '1px solid transparent',
          fontSize: 12,
          fontWeight: 500,
          transition: 'all .12s ease',
        }}
      >
        <Icon d={ICONS[icon]} />
        <span style={{ flex: 1 }}>{label}</span>
        {badge !== undefined && (
          <span
            style={{
              background: bc.bg,
              color: bc.color,
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
              padding: '2px 6px',
              borderRadius: 3,
              fontWeight: 600,
            }}
          >
            {badge}
          </span>
        )}
      </div>
    </Link>
  )
}

function Topbar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const pathname = usePathname()
  const clock = useISTClock()
  const { connected } = useWebSocket()
  const { criticalCount, warningCount } = useAlerts(undefined, false)
  const totalAlerts = criticalCount + warningCount

  return (
    <div
      style={{
        height: 52,
        background: 'var(--bg-1)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: 20,
        flexShrink: 0,
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 7,
            background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 11,
            fontWeight: 700,
            color: '#fff',
            fontFamily: 'var(--font-mono)',
          }}
        >
          KM
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, letterSpacing: -0.3 }}>
            KMRL <span style={{ color: 'var(--blue)' }}>NexusAI</span>
          </div>
          <div style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-2)', letterSpacing: 1, textTransform: 'uppercase' }}>
            Train Induction Platform
          </div>
        </div>
      </div>

      <div style={{ width: 1, height: 20, background: 'var(--border-2)' }} />

      <nav style={{ display: 'flex', gap: 2, minWidth: 0 }}>
        {PRIMARY_NAV.map(item => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`)
          return (
            <Link key={item.href} href={item.href} style={{ textDecoration: 'none' }}>
              <button
                style={{
                  padding: '5px 12px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 12,
                  fontWeight: 500,
                  fontFamily: 'var(--font-sans)',
                  color: active ? 'var(--blue)' : 'var(--text-1)',
                  background: active ? 'var(--bg-4)' : 'transparent',
                  border: active ? '1px solid var(--border-2)' : '1px solid transparent',
                  transition: 'all .12s',
                  whiteSpace: 'nowrap',
                }}
              >
                {item.label}
              </button>
            </Link>
          )
        })}
      </nav>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button className="btn btn-outline" onClick={onOpenPalette} style={{ fontSize: 11, padding: '5px 10px' }}>
          Search / Command
        </button>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            color: connected ? 'var(--emerald)' : 'var(--text-2)',
            background: connected ? 'var(--emerald-glow)' : 'var(--bg-2)',
            border: `1px solid ${connected ? 'rgba(16,185,129,.2)' : 'var(--border)'}`,
            padding: '4px 10px',
            borderRadius: 20,
          }}
        >
          <LivePulse color={connected ? '#10b981' : '#64748b'} />
          LIVE OPS
        </div>

        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--text-1)',
            background: 'var(--bg-2)',
            padding: '4px 10px',
            borderRadius: 5,
            border: '1px solid var(--border)',
          }}
        >
          {clock} IST
        </div>

        <Link href="/alerts" style={{ textDecoration: 'none' }}>
          <div
            style={{
              width: 32,
              height: 32,
              background: 'var(--bg-2)',
              border: `1px solid ${totalAlerts > 0 ? 'rgba(245,158,11,.3)' : 'var(--border)'}`,
              borderRadius: 7,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              position: 'relative',
              fontSize: 16,
              color: 'var(--text-1)',
            }}
          >
            !
            {totalAlerts > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: 4,
                  right: 4,
                  width: 8,
                  height: 8,
                  background: criticalCount > 0 ? 'var(--red)' : 'var(--amber)',
                  borderRadius: '50%',
                  border: '1.5px solid var(--bg-1)',
                }}
              />
            )}
          </div>
        </Link>
      </div>
    </div>
  )
}

function Sidebar() {
  const { criticalCount, warningCount } = useAlerts(undefined, false)
  const totalAlerts = criticalCount + warningCount

  return (
    <div
      style={{
        width: 200,
        background: 'var(--bg-1)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        padding: 12,
        gap: 2,
        flexShrink: 0,
        overflowY: 'auto',
      }}
    >
      <SidebarSection title="Operations" />
      <NavItem href="/dashboard" icon="dashboard" label="Command Center" />
      <NavItem href="/fleet" icon="fleet" label="Fleet Status" badge={25} badgeType="ok" />
      <NavItem href="/scheduler" icon="schedule" label="AI Scheduler" />
      <NavItem href="/depot" icon="depot" label="Depot View" />

      <SidebarSection title="Intelligence" />
      <NavItem href="/maintenance" icon="maintenance" label="Maintenance AI" badge={3} badgeType="warn" />
      <NavItem href="/analytics" icon="analytics" label="Analytics" />
      <NavItem href="/executive" icon="dashboard" label="Executive View" />
      <NavItem
        href="/alerts"
        icon="alerts"
        label="Alerts"
        badge={totalAlerts > 0 ? totalAlerts : undefined}
        badgeType={criticalCount > 0 ? 'critical' : 'warn'}
      />

      <SidebarSection title="System" />
      <NavItem href="/settings" icon="settings" label="Settings" />

      <div style={{ marginTop: 'auto', paddingTop: 12, borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 10, color: 'var(--text-2)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              background: 'linear-gradient(135deg,#3b82f6,#8b5cf6)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 9,
              color: '#fff',
              fontWeight: 700,
            }}
          >
            DC
          </span>
          <div>
            <div style={{ color: 'var(--text-1)', fontWeight: 600 }}>Depot Controller</div>
            <div>Muttom · v2.4.1</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function CommandPalette({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const router = useRouter()
  const [query, setQuery] = useState('')

  const filtered = useMemo(
    () =>
      COMMAND_ITEMS.filter(item =>
        item.label.toLowerCase().includes(query.toLowerCase()) ||
        item.href.toLowerCase().includes(query.toLowerCase())
      ),
    [query]
  )

  if (!open) return null

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(2, 6, 12, .72)',
        backdropFilter: 'blur(10px)',
        zIndex: 300,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: 72,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: 'min(680px, calc(100vw - 32px))',
          background: 'linear-gradient(180deg, rgba(18,25,34,.96), rgba(8,12,16,.98))',
          border: '1px solid rgba(59,130,246,.18)',
          borderRadius: 14,
          boxShadow: '0 24px 80px rgba(0,0,0,.45)',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: 14, borderBottom: '1px solid var(--border)' }}>
          <input
            autoFocus
            className="input"
            placeholder="Jump to dashboard, fleet, maintenance, settings..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            style={{ width: '100%', fontSize: 13, padding: '10px 12px' }}
          />
        </div>

        <div style={{ maxHeight: 360, overflowY: 'auto', padding: 8 }}>
          {filtered.map(item => (
            <button
              key={item.id}
              onClick={() => {
                router.push(item.href)
                onClose()
              }}
              style={{
                width: '100%',
                background: 'transparent',
                border: '1px solid transparent',
                borderRadius: 10,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '11px 12px',
                color: 'var(--text-0)',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--blue)' }} />
              <span style={{ flex: 1 }}>
                <span style={{ display: 'block', fontSize: 12, fontWeight: 600 }}>{item.label}</span>
                <span style={{ display: 'block', fontSize: 10, color: 'var(--text-2)', marginTop: 3 }}>{item.href}</span>
              </span>
              <span style={{ fontSize: 10, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>{item.shortcut}</span>
            </button>
          ))}

          {filtered.length === 0 && (
            <div style={{ padding: 18, textAlign: 'center', fontSize: 11, color: 'var(--text-2)' }}>
              No commands matched this search.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function CommandBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        borderTop: '1px solid var(--border)',
        padding: '6px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        fontSize: 11,
        color: 'var(--text-2)',
        flexShrink: 0,
      }}
    >
      {[
        ['Ctrl+K', 'Command palette'],
        ['Ctrl+R', 'Run optimizer'],
        ['Ctrl+E', 'Executive view'],
        ['Ctrl+D', 'Depot view'],
      ].map(([key, label]) => (
        <span key={key} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <kbd
            style={{
              background: 'var(--bg-3)',
              border: '1px solid var(--border-2)',
              borderRadius: 3,
              padding: '1px 5px',
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-1)',
            }}
          >
            {key}
          </kbd>
          {label}
        </span>
      ))}
      <button
        onClick={onOpenPalette}
        style={{
          marginLeft: 'auto',
          background: 'transparent',
          border: 'none',
          color: 'var(--text-2)',
          cursor: 'pointer',
          fontSize: 10,
          padding: 0,
        }}
      >
        Quick actions
      </button>
      <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--emerald)' }} />
        Depot Controller: Arjun M. · Muttom Depot
      </span>
    </div>
  )
}

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false)

  useKeyboardShortcut('k', () => setPaletteOpen(true))

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--bg-0)',
        color: 'var(--text-0)',
      }}
    >
      <Topbar onOpenPalette={() => setPaletteOpen(true)} />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar />
        <main style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>{children}</main>
      </div>

      <CommandBar onOpenPalette={() => setPaletteOpen(true)} />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
