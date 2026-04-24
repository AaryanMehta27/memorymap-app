'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'

export default function ContactCaregiverPage() {
  const supabase = createClient()
  const [message, setMessage] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    const { data: { user } } = await supabase.auth.getUser()
    if (user) {
      await supabase.from('caregiver_messages').insert({ patient_id: user.id, message: message.trim() })
    }
    setLoading(false)
    setSent(true)
    setMessage('')
  }

  return (
    <main className="max-w-lg mx-auto px-4 py-8">
      <h1 className="text-2xl font-semibold text-gray-900 mb-1">Contact Caregiver</h1>
      <p className="text-sm text-gray-400 mb-6">Send a message to your caregiver.</p>
      {sent ? (
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 text-sm text-green-700">
          Message sent!
          <button onClick={() => setSent(false)} className="block mt-3 text-indigo-600 hover:underline">Send another</button>
        </div>
      ) : (
        <form onSubmit={handleSend} className="space-y-4">
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={4} required placeholder="Type your message here..." className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
          <button type="submit" disabled={loading || !message.trim()} className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition disabled:opacity-50">
            {loading ? 'Sending...' : 'Send message'}
          </button>
        </form>
      )}
    </main>
  )
}
