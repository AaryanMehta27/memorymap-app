'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

const SHAPES = [
  {
    id: 'rectangle',
    label: 'Rectangle',
    icon: (
      <svg viewBox="0 0 40 24" className="w-10 h-6" fill="currentColor">
        <rect x="1" y="1" width="38" height="22" rx="2" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    ),
  },
  {
    id: 'square',
    label: 'Square',
    icon: (
      <svg viewBox="0 0 28 28" className="w-7 h-7" fill="currentColor">
        <rect x="1" y="1" width="26" height="26" rx="2" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    ),
  },
  {
    id: 'l-shape',
    label: 'L-Shape',
    icon: (
      <svg viewBox="0 0 28 28" className="w-7 h-7">
        <path d="M2 2 h14 v10 h10 v14 h-24 z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: 'open-plan',
    label: 'Open Plan',
    icon: (
      <svg viewBox="0 0 40 28" className="w-10 h-7">
        <rect x="1" y="1" width="38" height="26" rx="2" fill="none" stroke="currentColor" strokeWidth="2" />
        <line x1="15" y1="1" x2="15" y2="18" stroke="currentColor" strokeWidth="2" />
      </svg>
    ),
  },
  {
    id: 'narrow',
    label: 'Narrow',
    icon: (
      <svg viewBox="0 0 16 36" className="w-4 h-9">
        <rect x="1" y="1" width="14" height="34" rx="2" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    ),
  },
]

export default function NewRoomPage() {
  const router = useRouter()
  const supabase = createClient()
  const [name, setName] = useState('')
  const [shape, setShape] = useState('rectangle')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSaving(true)

    const { data: { user } } = await supabase.auth.getUser()
    if (!user) { router.push('/auth/login'); return }

    const { data: homeRow } = await supabase
      .from('homes').select('id').eq('owner_id', user.id).single()

    if (!homeRow) { setError('Home not found.'); setSaving(false); return }

    const { error: insertError } = await supabase.from('rooms').insert({
      home_id: homeRow.id,
      name: name.trim(),
      shape,
    })

    setSaving(false)
    if (insertError) { setError(insertError.message); return }
    router.push('/dashboard')
  }

  return (
    <main className="max-w-lg mx-auto px-4 py-8">
      <button onClick={() => router.push('/dashboard')} className="text-sm text-gray-500 hover:text-gray-700 mb-5 flex items-center gap-1">
        ← Dashboard
      </button>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">Add a room</h1>

      <form onSubmit={handleCreate} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Room name</label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Bedroom, Kitchen"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">Room shape</label>
          <div className="grid grid-cols-3 gap-3">
            {SHAPES.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setShape(s.id)}
                className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition ${
                  shape === s.id
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                    : 'border-gray-200 text-gray-500 hover:border-gray-300'
                }`}
              >
                {s.icon}
                <span className="text-xs font-medium">{s.label}</span>
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={saving || !name.trim()}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition disabled:opacity-50"
        >
          {saving ? 'Creating...' : 'Create room'}
        </button>
      </form>
    </main>
  )
}
