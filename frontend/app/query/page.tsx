'use client'

import { useEffect, useRef, useState } from 'react'
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
  const [isListening, setIsListening] = useState(false)
  const [voiceSupported, setVoiceSupported] = useState(false)
  const [caregiverNotified, setCaregiverNotified] = useState(false)
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const tokenRef = useRef('')

  useEffect(() => {
    // Check voice support
    setVoiceSupported(
      typeof window !== 'undefined' &&
      !!(window.SpeechRecognition || (window as any).webkitSpeechRecognition)
    )

    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) { router.push('/auth/login'); return }
      const { data: homeData } = await supabase.from('homes').select('id').eq('owner_id', user.id).single()
      if (homeData) { setHomeId(homeData.id); return }
      const { data: roleRow } = await supabase.from('user_roles').select('home_id').eq('user_id', user.id).single()
      if (roleRow?.home_id) setHomeId(roleRow.home_id)
    })
  }, [])

  function startVoice() {
    const SR: typeof SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) return

    // Toggle off if already listening
    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop()
      return
    }

    const recognition = new SR()
    recognitionRef.current = recognition
    recognition.lang = 'en-US'
    recognition.continuous = false
    recognition.interimResults = false

    recognition.onstart = () => setIsListening(true)
    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => setIsListening(false)

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript
      setQuestion(transcript)
      // Auto-submit after a short delay so user can see what was recognised
      setTimeout(() => performAsk(transcript), 600)
    }

    recognition.start()
  }

  async function performAsk(q: string) {
    if (!homeId || !q.trim()) return
    setLoading(true)
    setError('')
    setAnswer('')
    setSourceTags([])
    setCaregiverNotified(false)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token ?? ''
      tokenRef.current = token
      const result = await queryHome(homeId, q, token)
      setAnswer(result.answer ?? '')
      setSourceTags(result.source_tags ?? [])

      if (result.urgent_repeat) {
        setCaregiverNotified(true)
        fireUrgentNotification()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    await performAsk(question)
  }

  function fireUrgentNotification() {
    if (!('Notification' in window)) return
    const show = () => new Notification('MemoryMap — Caregiver Notified', {
      body: 'You have asked about this item many times. Your caregiver has been alerted.',
      icon: '/icon.svg',
    })
    if (Notification.permission === 'granted') {
      show()
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then(p => { if (p === 'granted') show() })
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
          <div className="flex-1 flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={isListening ? 'Listening…' : 'e.g. Where are my glasses?'}
              className={`flex-1 border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition ${
                isListening ? 'border-red-300 bg-red-50' : 'border-gray-300'
              }`}
            />
            {voiceSupported && (
              <button
                type="button"
                onClick={startVoice}
                title={isListening ? 'Stop listening' : 'Speak your question'}
                className={`rounded-lg px-3 py-2.5 border transition ${
                  isListening
                    ? 'border-red-400 bg-red-50 text-red-600 animate-pulse'
                    : 'border-gray-300 text-gray-400 hover:text-gray-600 hover:bg-gray-50'
                }`}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                </svg>
              </button>
            )}
          </div>
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg px-5 py-2.5 transition disabled:opacity-50 whitespace-nowrap"
          >
            {loading ? 'Searching…' : 'Ask'}
          </button>
        </form>

        {isListening && (
          <p className="text-xs text-red-500 mt-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse inline-block" />
            Listening — speak your question now
          </p>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-4">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {caregiverNotified && !loading && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 mb-4 flex items-start gap-2">
          <span className="text-lg leading-none">⚠️</span>
          <p className="text-sm text-amber-800 font-medium">
            You&apos;ve asked about this several times — your caregiver has been alerted and will check in soon.
          </p>
        </div>
      )}

      {loading && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 flex items-center justify-center gap-3">
          <div className="w-5 h-5 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
          <span className="text-sm text-gray-500">Looking through your home…</span>
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
          {voiceSupported ? (
            <p className="text-sm">Type a question above or tap the <strong>mic button</strong> to speak.</p>
          ) : (
            <p className="text-sm">Type a question above to find something in your home.</p>
          )}
        </div>
      )}
    </main>
  )
}
