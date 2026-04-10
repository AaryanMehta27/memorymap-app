'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

const SHAPES = [
  { value: 'rectangle', label: 'Rectangle', icon: '▭' },
  { value: 'l-shape', label: 'L-shape', icon: '⌐' },
]

export default function NewRoomPage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [shape, setShape] = useState('rectangle')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const supabase = createClient()
    const { data: { session } } = await supabase.auth.getSession()
    const user = session?.user
    if (!user) { router.push('/auth/login'); return }

    let { data: home } = await supabase
      .from('homes')
      .select('id')
      .eq('owner_id', user.id)
      .single()

    // Create home if missing
    if (!home) {
      const { data: newHome, error: insertErr } = await supabase
        .from('homes')
        .insert({ owner_id: user.id, name: 'My Home' })
        .select('id')
        .single()
      if (insertErr) { setError(`Home create error: ${insertErr.message}`); setLoading(false); return }
      home = newHome
    }

    if (!home) { setError('Could not find your home.'); setLoading(false); return }

    const { data: room, error: insertError } = await supabase
      .from('rooms')
      .insert({ home_id: home.id, name: name.trim(), shape })
      .select('id')
      .single()

    setLoading(false)

    if (insertError) { setError(insertError.message); return }

    router.push(`/rooms/${room.id}`)
  }

  return (
    <main className="max-w-lg mx-auto px-4 py-8">
      <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-700 mb-6 flex items-center gap-1">
        ← Back
      </button>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">Add a room</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Room name</label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="e.g. Bedroom, Kitchen, Living room"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Room shape</label>
          <div className="flex gap-3">
            {SHAPES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => setShape(s.value)}
                className={`flex-1 border-2 rounded-xl py-3 flex flex-col items-center gap-1 text-sm font-medium transition ${
                  shape === s.value
                    ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <span className="text-2xl">{s.icon}</span>
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading || !name.trim()}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg py-2.5 text-sm transition disabled:opacity-50"
        >
          {loading ? 'Creating...' : 'Create room'}
        </button>
      </form>
    </main>
  )
}
