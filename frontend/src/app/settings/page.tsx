'use client'

import React, { useState } from 'react'
import { Card, SectionHeader } from '@/components/ui'

const ALERT_CHANNELS = [
  { id: 'dashboard', label: 'Dashboard alerts', desc: 'Surface incidents directly in the live operations shell.' },
  { id: 'email', label: 'Email digests', desc: 'Send summaries to role-based distribution lists every shift.' },
  { id: 'sms', label: 'SMS escalation', desc: 'Escalate only critical operational incidents after threshold rules.' },
]

const ROLE_PROFILES = [
  { role: 'Depot Controller', focus: 'Bay conflicts, shunting windows, induction execution' },
  { role: 'Maintenance Supervisor', focus: 'Predictive failures, job cards, certification risk' },
  { role: 'Operations Manager', focus: 'Fleet readiness, SLA adherence, AI override rate' },
]

export default function SettingsPage() {
  const [darkMode, setDarkMode] = useState(true)
  const [motion, setMotion] = useState(true)
  const [commandHints, setCommandHints] = useState(true)

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, animation: 'fade-up .25s ease' }}>
      <SectionHeader
        title="Settings"
        subtitle="Operational preferences, command surface behavior, and alert routing"
        actions={<button className="btn btn-primary">Save Preferences</button>}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.1fr) minmax(280px, .9fr)', gap: 16 }}>
        <Card title="Workspace Preferences">
          <div style={{ display: 'grid', gap: 10 }}>
            {[
              {
                label: 'Dark operations theme',
                value: darkMode,
                setValue: setDarkMode,
                desc: 'Keeps the command center in the cinematic dark theme requested for operations screens.',
              },
              {
                label: 'Motion system',
                value: motion,
                setValue: setMotion,
                desc: 'Enables hover depth, loading shimmer, and state-transition animations.',
              },
              {
                label: 'Shortcut hints',
                value: commandHints,
                setValue: setCommandHints,
                desc: 'Shows command palette and quick-action shortcuts in the shell footer.',
              },
            ].map(item => (
              <label
                key={item.label}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  padding: '12px 14px',
                  background: 'var(--bg-2)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={item.value}
                  onChange={e => item.setValue(e.target.checked)}
                  style={{ marginTop: 2, accentColor: 'var(--blue)' }}
                />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-0)' }}>{item.label}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 3 }}>{item.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </Card>

        <Card title="Role Profiles">
          <div style={{ display: 'grid', gap: 8 }}>
            {ROLE_PROFILES.map(profile => (
              <div
                key={profile.role}
                style={{
                  padding: '12px 14px',
                  background: 'linear-gradient(180deg, rgba(59,130,246,.07), rgba(13,18,25,.85))',
                  border: '1px solid rgba(59,130,246,.18)',
                  borderRadius: 8,
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-0)', marginBottom: 4 }}>{profile.role}</div>
                <div style={{ fontSize: 11, color: 'var(--text-2)' }}>{profile.focus}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="Alert Routing">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
          {ALERT_CHANNELS.map(channel => (
            <div
              key={channel.id}
              style={{
                padding: '12px 14px',
                background: 'var(--bg-2)',
                border: '1px solid var(--border)',
                borderRadius: 8,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-0)', marginBottom: 4 }}>{channel.label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 10 }}>{channel.desc}</div>
              <button className="btn btn-outline" style={{ fontSize: 11 }}>Configure</button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
