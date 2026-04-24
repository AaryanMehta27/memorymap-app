'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

export function Nav() {
  const pathname = usePathname()
  const router = useRouter()
  const supabase = createClient()
  const [role, setRole] = useState<string | null>(null)

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) return
      const { data } = await supabase
        .from('user_roles').select('role').eq('user_id', user.id).single()
      setRole(data?.role ?? null)
    })
  }, [pathname])

  async function handleSignOut() {
    await supabase.auth.signOut()
    router.push('/auth/login')
  }

  if (!role) return null

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + '/')

  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-6 py-0 flex items-center justify-between h-14">
        <Link href="/dashboard" className="flex items-center gap-2">
          <span className="text-indigo-600 font-bold text-lg tracking-tight">MemoryMap</span>
        </Link>

        <div className="flex items-center gap-1">
          <Link
            href="/dashboard"
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition ${isActive('/dashboard') ? 'bg-indigo-50 text-indigo-700' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'}`}
          >
            Dashboard
          </Link>
          <Link
            href="/query"
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition ${isActive('/query') ? 'bg-indigo-50 text-indigo-700' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'}`}
          >
            Find Item
          </Link>
          <Link
            href="/alerts"
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition ${isActive('/alerts') ? 'bg-indigo-50 text-indigo-700' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'}`}
          >
            Alerts
          </Link>
          <Link
            href="/settings"
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition ${isActive('/settings') ? 'bg-indigo-50 text-indigo-700' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'}`}
          >
            Settings
          </Link>
          <div className="w-px h-4 bg-gray-200 mx-1" />
          <button
            onClick={handleSignOut}
            className="text-sm font-medium px-3 py-1.5 rounded-lg text-gray-500 hover:text-red-600 hover:bg-red-50 transition"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  )
}
