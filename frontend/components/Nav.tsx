'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { useEffect, useState } from 'react'
import type { User } from '@supabase/supabase-js'

export function Nav() {
  const pathname = usePathname()
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [role, setRole] = useState<string | null>(null)

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user)
      if (data.user) {
        supabase
          .from('user_roles')
          .select('role')
          .eq('user_id', data.user.id)
          .single()
          .then(({ data: r }) => setRole(r?.role ?? null))
      }
    })
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, session) => {
      setUser(session?.user ?? null)
      if (!session?.user) setRole(null)
    })
    return () => subscription.unsubscribe()
  }, [])

  const isAuth = pathname.startsWith('/auth')
  if (isAuth || !user) return null

  async function handleSignOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/auth/login')
  }

  return (
    <nav className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
      <Link href={role === 'patient' ? '/query' : '/dashboard'} className="font-semibold text-indigo-600 text-lg">
        MemoryMap
      </Link>

      <div className="flex items-center gap-4 text-sm">
        {role === 'caregiver' && (
          <>
            <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link href="/query" className="text-gray-600 hover:text-gray-900">Query</Link>
          </>
        )}
        {role === 'patient' && (
          <Link href="/query" className="text-gray-600 hover:text-gray-900">Find things</Link>
        )}
        <Link href="/settings" className="text-gray-600 hover:text-gray-900">Settings</Link>
        <button
          onClick={handleSignOut}
          className="text-gray-500 hover:text-red-600 transition"
        >
          Sign out
        </button>
      </div>
    </nav>
  )
}
