'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { queryHome } from '@/lib/ai-client'

interface SourceTag {
  label: string
  room_name: string
  position: string
  photo_url?: string | null
}

export default function QueryPage() {
  const router = useRouter()
  const supabase = createClient()
  const [homeId, setHomeId] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sourceTags, setSourceTags] = useState<SourceTag[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) { router.push('/auth/login'); return }
      const { data: homeData } = await supabase.from('homes').select('id').eq('owner_id', user.id).single()
      if (homeData) { setHomeId(homeData.id); return }
      const { data: roleRow } = await supabase.from('user_roles').select('home_id').eq('user_id', user.id).single()
      if (roleRow?.home_id) setHomeId(roleRow.home_id)
    })
  }, [])

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    if (!homeId || !question.trim()) return
    setLoading(true)
    setError('')
    setAnswer('')
    setSourceTags([])
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token ?? ''
      const result = await queryHome(homeId, question, token)
      setAnswer(result.answer ?? '')
      setSourceTags(result.source_tags ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Find an Item</h1>
        <p className="text-sm text-gray-500 mt-1">Ask where something is in your home and get an instant answer.</p>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 mb-6">
        <form onSubmit={handleAsk} className="flex gap-3">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Where are my glasses?"
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg px-5 py-2.5 transition disabled:opacity-50 whitespace-nowrap"
          >
            {loading ? 'Searching...' : 'Ask'}
          </button>
        </form>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-4">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {loading && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 flex items-center justify-center gap-3">
          <div className="w-5 h-5 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
          <span className="text-sm text-gray-500">Looking through your home...</span>
        </div>
      )}

      {answer && !loading && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 mb-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center shrink-0 mt-0.5">
              <svg className="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
            </div>
            <p className="text-gray-800 leading-relaxed text-sm">{answer}</p>
          </div>
        </div>
      )}

      {sourceTags.length > 0 && !loading && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-1">Sources</p>
          <div className="space-y-2">
            {sourceTags.map((tag, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-xl px-4 py-3 flex items-center gap-3 text-sm">
                <div className="w-2 h-2 rounded-full bg-indigo-400 shrink-0" />
                <span className="font-medium text-gray-800">{tag.label}</span>
                <span className="text-gray-300">·</span>
                <span className="text-gray-500">{tag.room_name}</span>
                <span className="text-gray-300">·</span>
                <span className="text-gray-500">{tag.position}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!answer && !loading && !error && (
        <div className="text-center py-16 text-gray-400">
          <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <p className="text-sm">Type a question above to find something in your home.</p>
        </div>
      )}
    </main>
  )
}
