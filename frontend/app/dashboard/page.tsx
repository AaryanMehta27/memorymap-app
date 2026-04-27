'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { RoomGrid } from '@/components/RoomGrid'

interface Room {
  id: string
  name: string
  shape: string
  photoCount: number
  tagCount: number
}

interface Alert {
  id: string
  level: 'info' | 'warning' | 'urgent'
  message: string
  alert_type: string
  timestamp: string
  acknowledged: boolean
}

const AI_BASE_URL = process.env.NEXT_PUBLIC_AI_API_URL

const ALERT_LEVEL_STYLES: Record<string, string> = {
  urgent: 'bg-red-50 border-red-300 text-red-800',
  warning: 'bg-amber-50 border-amber-300 text-amber-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
}

const ALERT_LEVEL_ICONS: Record<string, string> = {
  urgent: '🚨',
  warning: '⚠️',
  info: 'ℹ️',
}

export default function DashboardPage() {
  const router = useRouter()
  const [home, setHome] = useState<{ id: string; name: string } | null>(null)
  const [importantItems, setImportantItems] = useState<string[]>([])
  const [newItem, setNewItem] = useState('')
  const [itemsSaving, setItemsSaving] = useState(false)
  const [rooms, setRooms] = useState<Room[]>([])
  const [loading, setLoading] = useState(true)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [token, setToken] = useState<string>('')
  const [notifPermission, setNotifPermission] = useState<NotificationPermission | 'unsupported'>('default')

  // Keep a ref so the polling interval can access current alerts without stale closure
  const alertsRef = useRef<Alert[]>([])
  useEffect(() => { alertsRef.current = alerts }, [alerts])

  useEffect(() => {
    // Check notification support and current permission
    if (!('Notification' in window)) {
      setNotifPermission('unsupported')
    } else {
      setNotifPermission(Notification.permission)
    }
  }, [])

  useEffect(() => {
    const supabase = createClient()

    async function loadDashboard() {
      const { data: { session }, error: sessionError } = await supabase.auth.getSession()
      console.log('session:', session?.user?.id, 'error:', sessionError)
      const user = session?.user
      if (!user) { router.push('/auth/login'); return }

      const accessToken = session?.access_token ?? ''
      setToken(accessToken)

      const { data: roleRow, error: roleError } = await supabase
        .from('user_roles').select('role').eq('user_id', user.id).single()
      console.log('roleRow:', roleRow, 'roleError:', roleError)

      let { data: homeData, error: homeError } = await supabase
        .from('homes').select('id, name, important_items').eq('owner_id', user.id).single()
      console.log('homeData:', homeData, 'homeError:', homeError)

      if (!homeData) {
        const { data: newHome, error: insertError } = await supabase
          .from('homes')
          .insert({ owner_id: user.id, name: 'My Home' })
          .select('id, name')
          .single()
        console.log('newHome:', newHome, 'insertError:', insertError)
        homeData = newHome
      }

      if (!homeData) {
        setLoading(false)
        return
      }

      if (!roleRow) {
        await supabase.from('user_roles').insert({
          user_id: user.id,
          role: 'patient',
          home_id: homeData.id,
        })
      }

      setHome({ id: homeData.id, name: homeData.name })
      setImportantItems((homeData as { important_items?: string[] }).important_items ?? [])

      const { data: roomData } = await supabase
        .from('rooms')
        .select('id, name, shape, created_at, photos(count), tags(count)')
        .eq('home_id', homeData.id)
        .order('created_at', { ascending: true })

      const mapped = (roomData ?? []).map((r: Record<string, unknown>) => ({
        id: r.id,
        name: r.name,
        shape: r.shape,
        photoCount: (r.photos as unknown as { count: number }[])[0]?.count ?? 0,
        tagCount: (r.tags as unknown as { count: number }[])[0]?.count ?? 0,
      }))
      setRooms(mapped)
      setLoading(false)

      // Initial alert load
      if (accessToken) {
        try {
          const res = await fetch(`${AI_BASE_URL}/api/alerts/${homeData.id}`, {
            headers: { Authorization: `Bearer ${accessToken}` },
          })
          if (res.ok) {
            const data = await res.json()
            setAlerts(data.alerts ?? [])
          }
        } catch (e) {
          console.warn('Could not load alerts:', e)
        }
      }
    }

    loadDashboard()
  }, [router])

  // Poll for new alerts every 30 seconds; show browser notification on new urgent ones
  useEffect(() => {
    if (!home?.id || !token) return

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${AI_BASE_URL}/api/alerts/${home.id}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) return
        const data = await res.json()
        const fetched: Alert[] = data.alerts ?? []

        const knownIds = new Set(alertsRef.current.map(a => a.id))
        const fresh = fetched.filter(a => !knownIds.has(a.id) && !a.acknowledged)

        if (fresh.length > 0) {
          setAlerts(fetched)
          // Browser notification for new urgent alerts
          const urgentFresh = fresh.filter(a => a.level === 'urgent')
          if (urgentFresh.length > 0 && typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
            new Notification('MemoryMap — Urgent Patient Alert', {
              body: urgentFresh[0].message,
              icon: '/icon.svg',
            })
          }
        }
      } catch {
        // silent — network may be unavailable
      }
    }, 30_000)

    return () => clearInterval(interval)
  }, [home?.id, token])

  async function requestNotificationPermission() {
    if (!('Notification' in window)) return
    const permission = await Notification.requestPermission()
    setNotifPermission(permission)
  }

  function handleAddItem() {
    const trimmed = newItem.trim().toLowerCase()
    if (!trimmed || importantItems.includes(trimmed)) return
    setImportantItems((prev) => [...prev, trimmed])
    setNewItem('')
  }

  async function handleSaveItems() {
    if (!home) return
    setItemsSaving(true)
    const supabase = createClient()
    await supabase.from('homes').update({ important_items: importantItems }).eq('id', home.id)
    setItemsSaving(false)
  }

  async function handleAcknowledge(alertId: string) {
    try {
      const res = await fetch(`${AI_BASE_URL}/api/alerts/${alertId}/acknowledge`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        setAlerts((prev) => prev.map((a) => a.id === alertId ? { ...a, acknowledged: true } : a))
      }
    } catch (e) {
      console.warn('Could not acknowledge alert:', e)
    }
  }

  const unacknowledgedAlerts = alerts.filter((a) => !a.acknowledged)
  const urgentCount = unacknowledgedAlerts.filter((a) => a.level === 'urgent').length

  if (loading) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      </main>
    )
  }

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{home?.name}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{rooms.length} room{rooms.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Notification permission prompt */}
          {notifPermission === 'default' && (
            <button
              onClick={requestNotificationPermission}
              title="Enable browser notifications for urgent alerts"
              className="flex items-center gap-1.5 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-500 hover:bg-gray-50 transition"
            >
              🔔 Enable alerts
            </button>
          )}
          <Link
            href="/alerts"
            className="relative flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition"
          >
            🔔 Alerts
            {unacknowledgedAlerts.length > 0 && (
              <span className={`inline-flex items-center justify-center rounded-full text-xs font-bold px-1.5 py-0.5 min-w-[20px] ${urgentCount > 0 ? 'bg-red-500 text-white' : 'bg-amber-400 text-amber-900'}`}>
                {unacknowledgedAlerts.length}
              </span>
            )}
          </Link>
          <Link
            href="/rooms/new"
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition"
          >
            + Add room
          </Link>
        </div>
      </div>

      {/* Recent urgent alerts inline preview */}
      {urgentCount > 0 && (
        <div className="mb-6 space-y-2">
          {unacknowledgedAlerts.filter(a => a.level === 'urgent').slice(0, 2).map(alert => (
            <div key={alert.id} className={`border rounded-xl px-4 py-3 flex items-start justify-between gap-3 ${ALERT_LEVEL_STYLES[alert.level]}`}>
              <div className="flex items-start gap-2 min-w-0">
                <span className="text-lg shrink-0">{ALERT_LEVEL_ICONS[alert.level]}</span>
                <p className="text-sm font-medium leading-snug">{alert.message}</p>
              </div>
              <button
                onClick={() => handleAcknowledge(alert.id)}
                className="text-xs font-medium shrink-0 opacity-60 hover:opacity-100 underline whitespace-nowrap"
              >
                Dismiss
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Important items */}
      <div className="mb-8 bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex items-center justify-between mb-1">
          <h2 className="font-medium text-gray-800">Important items to track</h2>
        </div>
        <p className="text-sm text-gray-400 mb-4">
          The AI will search for these specifically in every photo analysis.
        </p>
        <div className="flex flex-wrap gap-2 mb-4">
          {importantItems.map((item) => (
            <span
              key={item}
              className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-700 text-sm font-medium rounded-full px-3 py-1"
            >
              {item}
              <button
                type="button"
                onClick={() => setImportantItems((prev) => prev.filter((i) => i !== item))}
                className="text-indigo-400 hover:text-indigo-700 ml-0.5 text-base leading-none"
                aria-label={`Remove ${item}`}
              >
                ×
              </button>
            </span>
          ))}
          {importantItems.length === 0 && (
            <p className="text-sm text-gray-400 italic">No items yet — add some below.</p>
          )}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddItem() } }}
            placeholder="e.g. reading glasses, hearing aid, blood pressure pill"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            type="button"
            onClick={handleAddItem}
            className="bg-white border border-gray-300 text-gray-700 text-sm font-medium rounded-lg px-4 py-2 hover:bg-gray-50 transition"
          >
            Add
          </button>
          <button
            type="button"
            onClick={handleSaveItems}
            disabled={itemsSaving}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition disabled:opacity-50"
          >
            {itemsSaving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>

      <RoomGrid rooms={rooms} />
    </main>
  )
}
