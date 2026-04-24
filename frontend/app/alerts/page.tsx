'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

interface Alert {
  id: string
  level: 'info' | 'warning' | 'urgent'
  message: string
  alert_type: string
  timestamp: string
  acknowledged: boolean
}

const LEVEL_STYLES: Record<string, string> = {
  urgent: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
}

const LEVEL_ICONS: Record<string, string> = {
  urgent: '🚨',
  warning: '⚠️',
  info: 'ℹ️',
}

const LEVEL_BADGE: Record<string, string> = {
  urgent: 'bg-red-100 text-red-700',
  warning: 'bg-amber-100 text-amber-700',
  info: 'bg-blue-100 text-blue-700',
}

const AI_BASE_URL = process.env.NEXT_PUBLIC_AI_API_URL

export default function AlertsPage() {
  const router = useRouter()
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState('')
  const [filter, setFilter] = useState<'all' | 'unread' | 'urgent'>('all')
  const [acknowledging, setAcknowledging] = useState<string | null>(null)

  useEffect(() => {
    const supabase = createClient()

    async function load() {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) { router.push('/auth/login'); return }

      const { data: homeData } = await supabase
        .from('homes').select('id').eq('owner_id', session.user.id).single()

      setToken(session.access_token)

      if (homeData && session.access_token) {
        try {
          const res = await fetch(`${AI_BASE_URL}/api/alerts/${homeData.id}`, {
            headers: { Authorization: `Bearer ${session.access_token}` },
          })
          if (res.ok) {
            const data = await res.json()
            setAlerts(data.alerts ?? [])
          }
        } catch (e) {
          console.warn('Could not load alerts:', e)
        }
      }

      setLoading(false)
    }

    load()
  }, [router])

  async function handleAcknowledge(alertId: string) {
    setAcknowledging(alertId)
    try {
      const res = await fetch(`${AI_BASE_URL}/api/alerts/${alertId}/acknowledge`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a))
      }
    } catch (e) {
      console.warn('Could not acknowledge:', e)
    } finally {
      setAcknowledging(null)
    }
  }

  async function handleAcknowledgeAll() {
    const unread = alerts.filter(a => !a.acknowledged)
    for (const alert of unread) {
      await handleAcknowledge(alert.id)
    }
  }

  const filtered = alerts.filter(a => {
    if (filter === 'unread') return !a.acknowledged
    if (filter === 'urgent') return a.level === 'urgent'
    return true
  })

  const unreadCount = alerts.filter(a => !a.acknowledged).length

  if (loading) {
    return (
      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      </main>
    )
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-8">
      <button onClick={() => router.push('/dashboard')} className="text-sm text-gray-500 hover:text-gray-700 mb-5 flex items-center gap-1">
        ← Dashboard
      </button>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Patient Alerts</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {unreadCount > 0 ? `${unreadCount} unread alert${unreadCount !== 1 ? 's' : ''}` : 'All caught up'}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            onClick={handleAcknowledgeAll}
            className="text-sm bg-white border border-gray-300 text-gray-700 rounded-lg px-4 py-2 hover:bg-gray-50 transition"
          >
            Dismiss all
          </button>
        )}
      </div>

      <div className="flex gap-2 mb-5">
        {(['all', 'unread', 'urgent'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs font-medium rounded-full px-3 py-1.5 transition capitalize ${filter === f ? 'bg-indigo-600 text-white' : 'bg-white border border-gray-300 text-gray-600 hover:bg-gray-50'}`}
          >
            {f}
            {f === 'unread' && unreadCount > 0 && (
              <span className="ml-1.5 bg-white text-indigo-600 rounded-full px-1.5 text-xs font-bold">{unreadCount}</span>
            )}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-4xl mb-3">✅</p>
          <p className="text-sm text-gray-500">
            {filter === 'all' ? 'No alerts yet. Alerts appear here when the patient shows signs of confusion or repeated questions.' : `No ${filter} alerts.`}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(alert => (
            <div
              key={alert.id}
              className={`border rounded-xl px-4 py-4 transition ${LEVEL_STYLES[alert.level] ?? 'bg-gray-50 border-gray-200 text-gray-700'} ${alert.acknowledged ? 'opacity-40' : ''}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex gap-3 items-start min-w-0">
                  <span className="text-xl shrink-0">{LEVEL_ICONS[alert.level] ?? 'ℹ️'}</span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium leading-snug">{alert.message}</p>
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className={`text-xs font-medium rounded-full px-2 py-0.5 capitalize ${LEVEL_BADGE[alert.level]}`}>
                        {alert.level}
                      </span>
                      <span className="text-xs opacity-60 capitalize">
                        {alert.alert_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs opacity-50">
                        {new Date(alert.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                        {' '}
                        {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>
                </div>
                {!alert.acknowledged && (
                  <button
                    onClick={() => handleAcknowledge(alert.id)}
                    disabled={acknowledging === alert.id}
                    className="text-xs font-medium shrink-0 opacity-60 hover:opacity-100 underline whitespace-nowrap disabled:opacity-30"
                  >
                    {acknowledging === alert.id ? '...' : 'Dismiss'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}
