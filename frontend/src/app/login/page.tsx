// ============================================================
// KMRL NexusAI — Login Page
// ============================================================
'use client'

import React, { FormEvent, useState } from 'react'
import { useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'

const ROLES_INFO = [
  { role: 'Depot Controller',       color: '#3b82f6', desc: 'Full plan control & overrides'  },
  { role: 'Maintenance Supervisor', color: '#f59e0b', desc: 'Job cards & predictive alerts'  },
  { role: 'Operations Manager',     color: '#10b981', desc: 'Fleet-wide KPIs & approval'     },
  { role: 'Branding Manager',       color: '#8b5cf6', desc: 'SLA compliance & contracts'     },
]

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail]       = useState('depot_controller@kmrl.in')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await authApi.login(email, password)
      router.push('/dashboard')
    } catch {
      setError('Invalid credentials. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', background: 'var(--bg-0)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, position: 'relative', overflow: 'hidden',
    }}>
      {/* Background grid */}
      <div style={{
        position: 'absolute', inset: 0, opacity: .03,
        backgroundImage: 'linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }} />

      {/* Ambient glow */}
      <div style={{
        position: 'absolute', top: '20%', left: '50%', transform: 'translateX(-50%)',
        width: 600, height: 400,
        background: 'radial-gradient(ellipse at center, rgba(59,130,246,.06) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div style={{ width: '100%', maxWidth: 440, position: 'relative', zIndex: 1 }}>

        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 13,
            background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 14px', fontSize: 18, fontWeight: 800,
            color: '#fff', fontFamily: 'var(--font-mono)',
            boxShadow: '0 0 30px rgba(59,130,246,.25)',
          }}>KM</div>
          <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: -.5, marginBottom: 4 }}>
            KMRL <span style={{ color: 'var(--blue)' }}>NexusAI</span>
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-2)', letterSpacing: .3 }}>
            Train Induction Planning & Scheduling Platform
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: 'var(--bg-1)', border: '1px solid var(--border)',
          borderRadius: 14, padding: 28,
          boxShadow: '0 8px 40px rgba(0,0,0,.5)',
        }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Sign in</h2>
          <p style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 22 }}>
            Access your operational dashboard
          </p>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', display: 'block', marginBottom: 5 }}>
                Email Address
              </label>
              <input
                data-cy="email"
                className="input"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@kmrl.in"
                required
                autoComplete="email"
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px' }}>
                  Password
                </label>
                <button type="button" style={{ fontSize: 11, color: 'var(--blue)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
                  Forgot?
                </button>
              </div>
              <input
                data-cy="password"
                className="input"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
              />
            </div>

            {error && (
              <div data-cy="error-msg" style={{
                padding: '8px 12px', background: 'rgba(239,68,68,.1)',
                border: '1px solid rgba(239,68,68,.25)', borderRadius: 6,
                fontSize: 12, color: '#ef4444',
              }}>
                {error}
              </div>
            )}

            <button
              data-cy="login-btn"
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{
                width: '100%', justifyContent: 'center', padding: '9px 0',
                fontSize: 13, marginTop: 4, borderRadius: 8,
                opacity: loading ? .7 : 1,
              }}
            >
              {loading ? '⟳ Signing in…' : 'Sign In →'}
            </button>
          </form>

          {/* Quick access hint */}
          <div style={{ marginTop: 20, padding: '12px 14px', background: 'var(--bg-2)', borderRadius: 8, border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 8 }}>
              Demo Account
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>
              depot_controller@kmrl.in
            </div>
            <button
              type="button"
              onClick={() => { setEmail('depot_controller@kmrl.in'); setPassword('kmrl@2025') }}
              style={{ marginTop: 6, fontSize: 10, color: 'var(--blue)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)', padding: 0 }}
            >
              Fill demo credentials →
            </button>
          </div>
        </div>

        {/* Role legend */}
        <div style={{ marginTop: 24 }}>
          <div style={{ fontSize: 10, color: 'var(--text-2)', textAlign: 'center', textTransform: 'uppercase', letterSpacing: '.8px', marginBottom: 12 }}>
            Platform Roles
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {ROLES_INFO.map(r => (
              <div key={r.role} style={{
                padding: '8px 10px', background: 'var(--bg-1)', border: '1px solid var(--border)',
                borderRadius: 7, display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: r.color, flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-0)' }}>{r.role}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-2)' }}>{r.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <p style={{ textAlign: 'center', marginTop: 20, fontSize: 10, color: 'var(--text-3)' }}>
          © 2025 Kochi Metro Rail Limited · KMRL NexusAI v2.4.1
        </p>
      </div>
    </div>
  )
}
