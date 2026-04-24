'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'

export default function RegisterPage() {
  const router = useRouter()
  const supabase = createClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { role: 'patient' } },
    })
    setLoading(false)
    if (error) { setError(error.message); return }
    router.push(`/auth/verify-otp?email=${encodeURIComponent(email)}&new=1`)
  }

  const leftPanel = (
    <div style={{ flex: 1, background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)', display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '60px', color: 'white' }} className="hidden md:flex">
      <div style={{ maxWidth: '400px' }}>
        <div style={{ fontSize: '28px', fontWeight: '800', letterSpacing: '-0.5px', marginBottom: '12px' }}>MemoryMap</div>
        <p style={{ fontSize: '22px', fontWeight: '600', lineHeight: '1.4', marginBottom: '24px', opacity: 0.95 }}>
          Helping loved ones find their way home.
        </p>
        <p style={{ fontSize: '15px', lineHeight: '1.7', opacity: 0.8 }}>
          A private, AI-powered assistant that helps people with memory difficulties locate their belongings — without relying on cloud services or subscriptions.
        </p>
        <div style={{ marginTop: '48px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {['Private & offline AI — no data leaves your home', 'Simple enough for any caregiver to set up', 'Warm, patient responses for memory-impaired users'].map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px', opacity: 0.9 }}>
              <div style={{ width: '20px', height: '20px', borderRadius: '50%', background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>✓</div>
              {f}
            </div>
          ))}
        </div>
      </div>
    </div>
  )

  return (
    <div style={{ minHeight: '100vh', display: 'flex', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      {leftPanel}

      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px', background: '#f9fafb' }}>
        <div style={{ width: '100%', maxWidth: '400px' }}>
          <div style={{ marginBottom: '32px' }}>
            <div style={{ fontSize: '22px', fontWeight: '700', color: '#4f46e5', marginBottom: '4px' }}>MemoryMap</div>
            <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#111827', margin: '0 0 6px' }}>Create your account</h1>
            <p style={{ fontSize: '14px', color: '#6b7280', margin: 0 }}>Get started with MemoryMap today.</p>
          </div>

          <div style={{ background: 'white', borderRadius: '16px', border: '1px solid #e5e7eb', padding: '32px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
            <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>Email address</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  style={{ width: '100%', border: '1.5px solid #d1d5db', borderRadius: '10px', padding: '10px 14px', fontSize: '14px', outline: 'none', boxSizing: 'border-box', background: '#fafafa' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>Password</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 6 characters"
                  style={{ width: '100%', border: '1.5px solid #d1d5db', borderRadius: '10px', padding: '10px 14px', fontSize: '14px', outline: 'none', boxSizing: 'border-box', background: '#fafafa' }}
                />
              </div>
              {error && (
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '10px', padding: '10px 14px' }}>
                  <p style={{ fontSize: '13px', color: '#dc2626', margin: 0 }}>{error}</p>
                </div>
              )}
              <button
                type="submit"
                disabled={loading}
                style={{ background: loading ? '#a5b4fc' : '#4f46e5', color: 'white', border: 'none', borderRadius: '10px', padding: '11px', fontSize: '14px', fontWeight: '600', cursor: loading ? 'not-allowed' : 'pointer', marginTop: '4px' }}
              >
                {loading ? 'Creating account...' : 'Create account'}
              </button>
            </form>
          </div>

          <p style={{ fontSize: '13px', color: '#9ca3af', textAlign: 'center', marginTop: '20px' }}>
            Already have an account?{' '}
            <Link href="/auth/login" style={{ color: '#4f46e5', fontWeight: '500', textDecoration: 'none' }}>Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
