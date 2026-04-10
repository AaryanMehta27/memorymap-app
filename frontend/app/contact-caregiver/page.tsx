'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

export default function ContactCaregiverPage() {
  const router = useRouter()
  const [phone, setPhone] = useState<string>('')
  const [editing, setEditing] = useState(false)
  const [newPhone, setNewPhone] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (!user) { router.push('/auth/login'); return }
      const p = user.user_metadata?.caregiver_phone ?? ''
      setPhone(p)
      setNewPhone(p)
      setLoading(false)
    })
  }, [router])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    const supabase = createClient()
    const { error } = await supabase.auth.updateUser({
      data: { caregiver_phone: newPhone.trim() },
    })
    setSaving(false)
    if (!error) {
      setPhone(newPhone.trim())
      setEditing(false)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    }
  }

  if (loading) {
    return (
      <main className="max-w-lg mx-auto px-4 py-8 flex justify-center">
        <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </main>
    )
  }

  return (
    <main className="max-w-lg mx-auto px-4 py-8">
      <h1 className="text-2xl font-semibold text-gray-900 mb-2">Contact Caregiver</h1>
      <p className="text-sm text-gray-500 mb-6">Reach your caregiver directly with one tap.</p>

      {phone && !editing ? (
        <div className="bg-white border border-gray-200 rounded-2xl p-6 text-center space-y-5">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Caregiver&apos;s number</p>
            <p className="text-3xl font-bold text-gray-900 tracking-wide">{phone}</p>
          </div>

          <div className="flex gap-3">
            <a
              href={`tel:${phone}`}
              className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl py-4 text-lg transition text-center"
            >
              📞 Call
            </a>
            <a
              href={`sms:${phone}`}
              className="flex-1 border-2 border-indigo-200 text-indigo-700 hover:bg-indigo-50 font-semibold rounded-xl py-4 text-lg transition text-center"
            >
              💬 Text
            </a>
          </div>

          <button
            onClick={() => setEditing(true)}
            className="text-sm text-gray-400 hover:text-gray-600 underline"
          >
            Change number
          </button>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-2xl p-6 space-y-4">
          {!phone && (
            <div className="text-center py-4 text-gray-400">
              <p className="text-4xl mb-2">📱</p>
              <p className="font-medium text-gray-700 mb-1">No caregiver number saved yet</p>
              <p className="text-sm">Add one below so you can call or text with one tap.</p>
            </div>
          )}

          <form onSubmit={handleSave} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Caregiver&apos;s phone number
              </label>
              <input
                type="tel"
                value={newPhone}
                onChange={(e) => setNewPhone(e.target.value)}
                placeholder="+1 (555) 000-0000"
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                autoFocus
              />
            </div>
            <div className="flex gap-2">
              {editing && (
                <button
                  type="button"
                  onClick={() => { setEditing(false); setNewPhone(phone) }}
                  className="flex-1 border border-gray-300 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50"
                >
                  Cancel
                </button>
              )}
              <button
                type="submit"
                disabled={saving || !newPhone.trim()}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg py-2 text-sm transition disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save number'}
              </button>
            </div>
          </form>
        </div>
      )}

      {saved && (
        <p className="text-sm text-green-600 text-center mt-3">Number saved successfully.</p>
      )}
    </main>
  )
}
