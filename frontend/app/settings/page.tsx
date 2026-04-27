'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

type DeleteStep = 'idle' | 'confirm' | 'otp' | 'deleting'

interface CaregiverInfo {
  name: string
  phone: string
  email: string
}

export default function SettingsPage() {
  const router = useRouter()
  const supabase = createClient()

  const [email, setEmail] = useState('')
  const [role, setRole] = useState('')
  const [homeId, setHomeId] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [pwSuccess, setPwSuccess] = useState('')
  const [pwError, setPwError] = useState('')
  const [pwLoading, setPwLoading] = useState(false)
  const [deleteStep, setDeleteStep] = useState<DeleteStep>('idle')
  const [deleteOtp, setDeleteOtp] = useState('')
  const [deleteError, setDeleteError] = useState('')

  const [caregiverInfo, setCaregiverInfo] = useState<CaregiverInfo>({ name: '', phone: '', email: '' })
  const [caregiverSaving, setCaregiverSaving] = useState(false)
  const [caregiverSuccess, setCaregiverSuccess] = useState('')
  const [caregiverError, setCaregiverError] = useState('')

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) { router.push('/auth/login'); return }
      setEmail(user.email ?? '')

      const [{ data: roleRow }, { data: homeData }] = await Promise.all([
        supabase.from('user_roles').select('role').eq('user_id', user.id).single(),
        supabase.from('homes').select('id, caregiver_info').eq('owner_id', user.id).single(),
      ])

      setRole(roleRow?.role ?? '')

      if (homeData) {
        setHomeId(homeData.id)
        const ci = (homeData as any).caregiver_info
        if (ci && typeof ci === 'object') {
          setCaregiverInfo({
            name: ci.name ?? '',
            phone: ci.phone ?? '',
            email: ci.email ?? '',
          })
        }
      }
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

  async function handleSaveCaregiverInfo(e: React.FormEvent) {
    e.preventDefault()
    if (!homeId) return
    setCaregiverSaving(true)
    setCaregiverError('')
    setCaregiverSuccess('')
    const { error } = await supabase
      .from('homes')
      .update({ caregiver_info: caregiverInfo })
      .eq('id', homeId)
    setCaregiverSaving(false)
    if (error) {
      setCaregiverError('Could not save. Make sure the caregiver_info column exists in your homes table.')
    } else {
      setCaregiverSuccess('Caregiver contact saved.')
    }
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
    const { data, error: verifyError } = await supabase.auth.verifyOtp({
      email, token: deleteOtp.trim(), type: 'email',
    })
    if (verifyError || !data.user) {
      setDeleteError(verifyError?.message ?? 'OTP verification failed.')
      setDeleteStep('otp')
      return
    }
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const res = await fetch('/api/delete-account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session?.access_token}` },
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
    <main className="max-w-2xl mx-auto px-4 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Manage your account and preferences.</p>
      </div>

      <div className="space-y-5">
        {/* Account info */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Account</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-500">Email</span>
              <span className="text-sm font-medium text-gray-900">{email}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-gray-500">Role</span>
              <span className="text-sm font-medium text-gray-900 capitalize">{role}</span>
            </div>
          </div>
        </div>

        {/* Caregiver contact */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-1">Caregiver Contact</h2>
          <p className="text-sm text-gray-400 mb-4">
            Add your caregiver&apos;s details. They will be alerted when you ask about the same item repeatedly.
          </p>
          <form onSubmit={handleSaveCaregiverInfo} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Caregiver name</label>
              <input
                type="text"
                value={caregiverInfo.name}
                onChange={(e) => setCaregiverInfo(p => ({ ...p, name: e.target.value }))}
                placeholder="e.g. Sarah Johnson"
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Phone number</label>
              <input
                type="tel"
                value={caregiverInfo.phone}
                onChange={(e) => setCaregiverInfo(p => ({ ...p, phone: e.target.value }))}
                placeholder="e.g. +44 7700 900123"
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Email address</label>
              <input
                type="email"
                value={caregiverInfo.email}
                onChange={(e) => setCaregiverInfo(p => ({ ...p, email: e.target.value }))}
                placeholder="e.g. sarah@example.com"
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            {caregiverError && <p className="text-sm text-red-600">{caregiverError}</p>}
            {caregiverSuccess && <p className="text-sm text-green-600">{caregiverSuccess}</p>}
            <button
              type="submit"
              disabled={caregiverSaving}
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg px-4 py-2 transition disabled:opacity-50"
            >
              {caregiverSaving ? 'Saving…' : 'Save caregiver contact'}
            </button>
          </form>
        </div>

        {/* Change password */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Change Password</h2>
          <form onSubmit={handleChangePassword} className="space-y-3">
            <input
              type="password"
              required
              minLength={6}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="New password (min 6 characters)"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
            {pwError && <p className="text-sm text-red-600">{pwError}</p>}
            {pwSuccess && <p className="text-sm text-green-600">{pwSuccess}</p>}
            <button
              type="submit"
              disabled={pwLoading}
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg px-4 py-2 transition disabled:opacity-50"
            >
              {pwLoading ? 'Saving…' : 'Update password'}
            </button>
          </form>
        </div>

        {/* Privacy */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Privacy</h2>
          <div className="space-y-2 text-sm text-gray-600">
            <p>Photos you upload are analysed by an AI model. They are not stored beyond what is needed to identify object locations.</p>
            <p>Your room data, tags, and account information are stored in a private database accessible only to your account.</p>
            <p>You can permanently delete all your data at any time using the option below.</p>
          </div>
        </div>

        {/* Danger zone */}
        <div className="bg-white rounded-2xl shadow-sm border border-red-200 p-6">
          <h2 className="text-sm font-semibold text-red-500 uppercase tracking-wider mb-1">Danger Zone</h2>
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
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 space-y-3">
              <p className="text-sm font-medium text-red-800">
                This will permanently delete all your rooms, photos, tags, and your account. This cannot be undone.
              </p>
              {deleteError && <p className="text-sm text-red-600">{deleteError}</p>}
              <div className="flex gap-2">
                <button onClick={() => setDeleteStep('idle')} className="border border-gray-300 text-gray-600 text-sm rounded-lg px-4 py-2 hover:bg-gray-50">Cancel</button>
                <button onClick={handleRequestDeleteOtp} className="bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-lg px-4 py-2 transition">
                  Continue — send verification code
                </button>
              </div>
            </div>
          )}

          {(deleteStep === 'otp' || deleteStep === 'deleting') && (
            <form onSubmit={handleConfirmDelete} className="bg-red-50 border border-red-200 rounded-xl p-4 space-y-3">
              <p className="text-sm text-red-800">
                A verification code was sent to <strong>{email}</strong>. Enter it below to confirm deletion.
              </p>
              <input
                type="text"
                required
                value={deleteOtp}
                onChange={(e) => setDeleteOtp(e.target.value)}
                maxLength={8}
                inputMode="numeric"
                placeholder="00000000"
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm tracking-widest text-center font-mono focus:outline-none focus:ring-2 focus:ring-red-400"
              />
              {deleteError && <p className="text-sm text-red-600">{deleteError}</p>}
              <div className="flex gap-2">
                <button type="button" onClick={() => { setDeleteStep('idle'); setDeleteOtp('') }} className="border border-gray-300 text-gray-600 text-sm rounded-lg px-4 py-2 hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={deleteStep === 'deleting' || deleteOtp.length < 6} className="bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-lg px-4 py-2 transition disabled:opacity-50">
                  {deleteStep === 'deleting' ? 'Deleting…' : 'Delete my account'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </main>
  )
}
