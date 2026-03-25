'use client'

import { useState, useRef, useEffect } from 'react'
import { createClient } from '@/lib/supabase/client'
import { queryHome } from '@/lib/ai-client'
import { useRouter } from 'next/navigation'

interface SourceTag {
  label: string
  position: string
  room_name: string
  photo_storage_path: string | null
}

interface QueryResult {
  answer: string
  source_tags: SourceTag[]
}

export default function QueryPage() {
  const router = useRouter()
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [homeId, setHomeId] = useState<string | null>(null)
  const [signedUrls, setSignedUrls] = useState<Record<string, string>>({})
  const inputRef = useRef<HTMLInputElement>(null)
  const supabase = createClient()

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) { router.push('/auth/login'); return }

      const { data: roleRow } = await supabase
        .from('user_roles').select('role, home_id').eq('user_id', user.id).single()

      if (roleRow?.home_id) {
        setHomeId(roleRow.home_id)
      } else {
        const { data: home } = await supabase
          .from('homes').select('id').eq('owner_id', user.id).single()
        if (home) setHomeId(home.id)
      }
    })
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim() || !homeId) return
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token ?? ''
      const res = await queryHome(homeId, question.trim(), token)
      setResult(res)

      if (typeof window !== 'undefined' && res.answer) {
        window.speechSynthesis.cancel()
        window.speechSynthesis.speak(new SpeechSynthesisUtterance(res.answer))
      }

      if (res.source_tags?.length) {
        const urls: Record<string, string> = {}
        for (const tag of res.source_tags) {
          if (tag.photo_storage_path) {
            const { data } = await supabase.storage
              .from('photos')
              .createSignedUrl(tag.photo_storage_path, 3600)
            if (data?.signedUrl) urls[tag.photo_storage_path] = data.signedUrl
          }
        }
        setSignedUrls(urls)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  function handleAskAgain() {
    setQuestion('')
    setResult(null)
    setError('')
    window.speechSynthesis?.cancel()
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  function handleVoiceInput() {
    const SR =
      (window as unknown as { SpeechRecognition?: new () => SpeechRecognition }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognition }).webkitSpeechRecognition
    if (!SR) return
    const recognition = new SR()
    recognition.onresult = (e: SpeechRecognitionEvent) => setQuestion(e.results[0][0].transcript)
    recognition.start()
  }

  return (
    <main className="min-h-[calc(100vh-56px)] flex flex-col max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Find something</h1>
      <p className="text-gray-500 mb-8 text-lg">Ask where something is in your home.</p>

      {!result && !loading && (
        <form onSubmit={handleSubmit} className="mt-auto">
          <label className="block text-base font-medium text-gray-700 mb-3">
            What are you looking for?
          </label>
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Where are my glasses?"
              className="flex-1 border border-gray-300 rounded-xl px-4 py-3 text-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              autoFocus
            />
            <button
              type="button"
              onClick={handleVoiceInput}
              className="border border-gray-300 rounded-xl px-4 py-3 text-gray-500 hover:bg-gray-50 transition text-xl"
              title="Use voice input"
            >
              🎤
            </button>
            <button
              type="submit"
              disabled={!question.trim() || !homeId}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl px-6 py-3 text-base transition disabled:opacity-50"
            >
              Ask
            </button>
          </div>
        </form>
      )}

      {loading && (
        <div className="mt-auto flex flex-col items-center justify-center py-16 text-center">
          <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4" />
          <p className="text-xl text-gray-600">Looking for your items...</p>
        </div>
      )}

      {error && (
        <div className="mt-8">
          <p className="text-red-600 text-base bg-red-50 border border-red-200 rounded-xl px-4 py-3">{error}</p>
          <button onClick={handleAskAgain} className="mt-4 text-indigo-600 hover:underline text-base">Try again</button>
        </div>
      )}

      {result && (
        <div className="mt-6 flex-1">
          <div className="bg-indigo-50 border border-indigo-200 rounded-2xl px-5 py-4 mb-6">
            <p className="text-xl text-gray-900 leading-relaxed">{result.answer}</p>
          </div>

          {result.source_tags?.length > 0 && (
            <div className="space-y-3 mb-8">
              {result.source_tags.map((tag, i) => (
                <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 flex gap-4 items-start">
                  {tag.photo_storage_path && signedUrls[tag.photo_storage_path] && (
                    <img
                      src={signedUrls[tag.photo_storage_path]}
                      alt={tag.label}
                      className="w-20 h-16 object-cover rounded-lg shrink-0"
                    />
                  )}
                  <div>
                    <p className="font-semibold text-gray-900 text-base">{tag.label}</p>
                    <p className="text-gray-500 text-sm">{tag.room_name} — {tag.position}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={handleAskAgain}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl py-3 text-base transition"
          >
            Ask again
          </button>
        </div>
      )}
    </main>
  )
}
