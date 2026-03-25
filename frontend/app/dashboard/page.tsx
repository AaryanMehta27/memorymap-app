import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { RoomGrid } from '@/components/RoomGrid'

export default async function DashboardPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/auth/login')

  // Check caregiver role
  const { data: roleRow } = await supabase
    .from('user_roles')
    .select('role, home_id')
    .eq('user_id', user.id)
    .single()

  if (roleRow?.role === 'patient') redirect('/query')

  // Get home
  const { data: home } = await supabase
    .from('homes')
    .select('id, name')
    .eq('owner_id', user.id)
    .single()

  if (!home) redirect('/auth/login')

  // Get rooms with photo/tag counts
  const { data: rooms } = await supabase
    .from('rooms')
    .select('id, name, shape, created_at, photos(count), tags(count)')
    .eq('home_id', home.id)
    .order('created_at', { ascending: true })

  const roomsWithCounts = (rooms ?? []).map((r) => ({
    id: r.id,
    name: r.name,
    shape: r.shape,
    photoCount: (r.photos as unknown as { count: number }[])[0]?.count ?? 0,
    tagCount: (r.tags as unknown as { count: number }[])[0]?.count ?? 0,
  }))

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{home.name}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{roomsWithCounts.length} room{roomsWithCounts.length !== 1 ? 's' : ''}</p>
        </div>
        <Link
          href="/rooms/new"
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition"
        >
          + Add room
        </Link>
      </div>

      {roomsWithCounts.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg mb-2">No rooms yet</p>
          <p className="text-sm">Add a room to start mapping your home.</p>
        </div>
      ) : (
        <RoomGrid rooms={roomsWithCounts} />
      )}
    </main>
  )
}
