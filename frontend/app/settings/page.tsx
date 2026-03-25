'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

type DeleteStep = 'idle' | 'confirm' | 'otp' | 'deleting'

export default function SettingsPage() {
  const router = useRouter()
  const supabase = createClient()

  const [email, setEmail] = useState('')
  const [role, setRole] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [pwSuccess, setPwSuccess] = useState('')
  const [pwError, setPwError] = useState('')
  const [pwLoading, setPwLoading] = useState(false)

  const [deleteStep, setDeleteStep] = useState<DeleteStep>('idle')
  const [deleteOtp, setDeleteOtp] = useState('')
  const [deleteError, setDeleteError] = useState('')

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) { router.push('/auth/login'); return }
      setEmail(user.email ?? '')
      const { data: roleRow } = await supabase
        .from('user_roles').select('role').eq('user_id', user.id).single()
      setRole(roleRow?.role ?? '')
    })
  }, [])

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault()
    setPwError('')
    setPwSuccess('')
    setPwLoading(true)
    const { error } = await supabase.auth.updateUser({ password: newPassword })
    setPwLoading(false)
    if (error) { setPwError(error.message); return }
    setPwSuccess('Password updated successfully.')
    setNewPassword('')
  }

  async function handleRequestDeleteOtp() {
    setDeleteError('')
    const { error } = await supabase.auth.signInWithOtp({ email })
    if (error) { setDeleteError(error.message); return }
    setDeleteStep('otp')
  }

  async function handleConfirmDelete(e: React.FormEvent) {
    e.preventDefault()
    setDeleteError('')
    setDeleteStep('deleting')

    // Verify OTP
    const { data, error: verifyError } = await supabase.auth.verifyOtp({
      email,
      token: deleteOtp.trim(),
      type: 'email',
    })

    if (verifyError || !data.user) {
      setDeleteError(verifyError?.message ?? 'OTP verification failed.')
      setDeleteStep('otp')
      return
    }

    // Call server action to delete account
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const res = await fetch('/api/delete-account', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.access_token}`,
        },
      })

      if (!res.ok) {
        const body = await res.json()
        setDeleteError(body.error ?? 'Deletion failed.')
        setDeleteStep('otp')
        return
      }

      await supabase.auth.signOut()
      router.push('/auth/login?message=account-deleted')
    } catch {
      setDeleteError('An unexpected error occurred.')
      setDeleteStep('otp')
    }
  }

  return (
    <main className="max-w-lg mx-auto px-4 py-8 space-y-8">
      <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>

      {/* Account info */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-2">
        <h2 className="font-medium text-gray-800 mb-3">Account</h2>
        <div className="text-sm text-gray-600">
          <span className="text-gray-400">Email: </span>{email}
        </div>
        <div className="text-sm text-gray-600">
          <span className="text-gray-400">Role: </span>
          <span className="capitalize">{role}</span>
        </div>
      </section>

      {/* Change password */}
      <section className="bg-white border border-gray-200 rounded-xl p-5">
        <h2 className="font-medium text-gray-800 mb-3">Change password</h2>
        <form onSubmit={handleChangePassword} className="space-y-3">
          <input
            type="password"
            required
            minLength={6}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="New password"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          {pwError && <p className="text-sm text-red-600">{pwError}</p>}
          {pwSuccess && <p className="text-sm text-green-600">{pwSuccess}</p>}
          <button
            type="submit"
            disabled={pwLoading}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition disabled:opacity-50"
          >
            {pwLoading ? 'Saving...' : 'Update password'}
          </button>
        </form>
      </section>

      {/* Privacy */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 text-sm text-gray-600 space-y-2">
        <h2 className="font-medium text-gray-800 mb-2">Privacy</h2>
        <p>Photos you capture are sent to Google Gemini API for object detection. They are not stored on MemoryMap servers.</p>
        <p>Your room maps, tags, and account data are stored in a private Supabase database, accessible only to your account.</p>
        <p>You can permanently delete all your data at any time using the button below.</p>
      </section>

      {/* Danger zone */}
      <section className="border border-red-200 rounded-xl p-5">
        <h2 className="font-medium text-red-700 mb-1">Danger zone</h2>
        <p className="text-sm text-gray-500 mb-4">Permanently delete your account and all associated data. This cannot be undone.</p>

        {deleteStep === 'idle' && (
          <button
            onClick={() => setDeleteStep('confirm')}
            className="border border-red-300 text-red-600 hover:bg-red-50 text-sm font-medium rounded-lg px-4 py-2 transition"
          >
            Delete my account
          </button>
        )}

        {deleteStep === 'confirm' && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-3">
            <p className="text-sm font-medium text-red-800">
              This will permanently delete all your rooms, photos, tags, and your account. This cannot be undone.
            </p>
            {deleteError && <p className="text-sm text-red-600">{deleteError}</p>}
            <div className="flex gap-2">
              <button
                onClick={() => setDeleteStep('idle')}
                className="border border-gray-300 text-gray-600 text-sm rounded-lg px-4 py-2 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRequestDeleteOtp}
                className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition"
              >
                Continue — send verification code
              </button>
            </div>
          </div>
        )}

        {(deleteStep === 'otp' || deleteStep === 'deleting') && (
          <form onSubmit={handleConfirmDelete} className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-3">
            <p className="text-sm text-red-800">
              A verification code was sent to <strong>{email}</strong>. Enter it below to confirm deletion.
            </p>
            <input
              type="text"
              required
              value={deleteOtp}
              onChange={(e) => setDeleteOtp(e.target.value)}
              maxLength={6}
              inputMode="numeric"
              placeholder="000000"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm tracking-widest text-center focus:outline-none focus:ring-2 focus:ring-red-400"
            />
            {deleteError && <p className="text-sm text-red-600">{deleteError}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => { setDeleteStep('idle'); setDeleteOtp('') }}
                className="border border-gray-300 text-gray-600 text-sm rounded-lg px-4 py-2 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={deleteStep === 'deleting' || deleteOtp.length < 6}
                className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition disabled:opacity-50"
              >
                {deleteStep === 'deleting' ? 'Deleting...' : 'Delete my account'}
              </button>
            </div>
          </form>
        )}
      </section>
    </main>
  )
}
