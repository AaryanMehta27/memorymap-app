'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

export default function VerifyOtpPage() {
  const router = useRouter()
  const [otp, setOtp] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const stored = sessionStorage.getItem('pending_email')
    if (!stored) router.push('/auth/register')
    else setEmail(stored)
  }, [router])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const supabase = createClient()
    const { data, error: verifyError } = await supabase.auth.verifyOtp({
      email,
      token: otp.trim(),
      type: 'signup',
    })

    if (verifyError) {
      setLoading(false)
      setError(verifyError.message)
      return
    }

    // Create home + user_roles record after verification
    const userId = data.user?.id
    if (userId) {
      // Insert home
      const { data: home } = await supabase
        .from('homes')
        .insert({ owner_id: userId, name: 'My Home' })
        .select('id')
        .single()

      if (home) {
        await supabase.from('user_roles').insert({
          user_id: userId,
          role: 'caregiver',
          home_id: home.id,
        })
      }
    }

    sessionStorage.removeItem('pending_email')
    setLoading(false)
    router.push('/dashboard')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
        <h1 className="text-2xl font-semibold text-gray-900 mb-1">Check your email</h1>
        <p className="text-sm text-gray-500 mb-6">
          We sent a 6-digit code to <span className="font-medium text-gray-700">{email}</span>.
          Enter it below to verify your account.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Verification code</label>
            <input
              type="text"
              required
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              maxLength={6}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm tracking-widest text-center focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="000000"
              inputMode="numeric"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || otp.length < 6}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg py-2.5 text-sm transition disabled:opacity-50"
          >
            {loading ? 'Verifying...' : 'Verify email'}
          </button>
        </form>
      </div>
    </div>
  )
}
