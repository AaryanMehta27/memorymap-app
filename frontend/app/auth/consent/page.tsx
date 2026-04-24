'use client'

import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

export default function ConsentPage() {
  const router = useRouter()
  const supabase = createClient()

  async function handleAccept() {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) { router.push('/auth/login'); return }
    const role = user.user_metadata?.role ?? 'patient'
    await supabase.from('user_roles').upsert({ user_id: user.id, role, home_id: null })
    router.push('/dashboard')
  }

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-indigo-600 tracking-tight mb-1">MemoryMap</h1>
          <p className="text-sm text-gray-500">Privacy &amp; Data Consent</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-indigo-50 mx-auto mb-5">
            <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>

          <h2 className="text-lg font-semibold text-gray-900 text-center mb-2">Before you continue</h2>
          <p className="text-sm text-gray-500 text-center mb-6">Please read how MemoryMap handles your data.</p>

          <div className="space-y-3 mb-6">
            {[
              { icon: '📷', text: 'Photos you upload are analysed by a local AI model to identify items.' },
              { icon: '🔒', text: 'All detected items are stored privately and linked only to your account.' },
              { icon: '👥', text: 'Only you and caregivers you invite can access your data.' },
              { icon: '🗑️', text: 'You can permanently delete all your data at any time from Settings.' },
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3 bg-gray-50 rounded-lg px-4 py-3">
                <span className="text-base shrink-0">{item.icon}</span>
                <p className="text-sm text-gray-600">{item.text}</p>
              </div>
            ))}
          </div>

          <button
            onClick={handleAccept}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg px-4 py-2.5 transition"
          >
            I understand — continue to MemoryMap
          </button>
        </div>
      </div>
    </main>
  )
}
