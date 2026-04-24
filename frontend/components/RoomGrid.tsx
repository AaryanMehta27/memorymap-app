'use client'

import Link from 'next/link'
import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'

interface Room {
  id: string
  name: string
  shape: string
  photoCount: number
  tagCount: number
}

function ShapeIcon({ shape }: { shape: string }) {
  switch (shape) {
    case 'square':    return <span className="text-xl">◻</span>
    case 'l-shape':   return <span className="text-xl">⌐</span>
    case 'open-plan': return <span className="text-xl">⊞</span>
    case 'narrow':    return <span className="text-xl text-sm">▬</span>
    default:          return <span className="text-xl">▭</span>
  }
}

function RoomCard({ room, onDeleted }: { room: Room; onDeleted: (id: string) => void }) {
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (!confirming) { setConfirming(true); return }

    setDeleting(true)
    const supabase = createClient()

    // 1. Get all photos for this room to delete from storage
    const { data: photos } = await supabase
      .from('photos')
      .select('id, storage_path')
      .eq('room_id', room.id)

    // 2. Delete each photo from storage
    if (photos && photos.length > 0) {
      const paths = photos.map((p) => p.storage_path)
      await supabase.storage.from('photos').remove(paths)
    }

    // 3. Delete tags, photos rows, then room (cascade order)
    await supabase.from('tags').delete().eq('room_id', room.id)
    await supabase.from('photos').delete().eq('room_id', room.id)
    await supabase.from('rooms').delete().eq('id', room.id)

    setDeleting(false)
    onDeleted(room.id)
  }

  return (
    <div className="relative">
      <Link
        href={`/rooms/${room.id}`}
        className="block bg-white border border-gray-200 rounded-xl p-5 pr-12 hover:shadow-md hover:border-indigo-300 transition"
      >
        <div className="flex items-start justify-between mb-3">
          <div className="w-10 h-10 bg-indigo-50 rounded-lg flex items-center justify-center text-indigo-600">
            <ShapeIcon shape={room.shape} />
          </div>
          <span className="text-xs text-gray-400 capitalize">{room.shape}</span>
        </div>
        <h3 className="font-medium text-gray-900">{room.name}</h3>
        <p className="text-xs text-gray-400 mt-1">
          {room.photoCount} photo{room.photoCount !== 1 ? 's' : ''} · {room.tagCount} tag{room.tagCount !== 1 ? 's' : ''}
        </p>
      </Link>

      {/* Delete button — always visible */}
      <div className="absolute top-3 right-3 z-10">
        {confirming ? (
          <div className="flex items-center gap-1.5 bg-white border border-red-200 rounded-lg px-2 py-1 shadow-sm">
            <span className="text-xs text-red-600 font-medium">Delete room?</span>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-xs bg-red-500 hover:bg-red-600 text-white rounded px-2 py-0.5 font-medium disabled:opacity-50"
            >
              {deleting ? '...' : 'Yes'}
            </button>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); setConfirming(false) }}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              No
            </button>
          </div>
        ) : (
          <button
            onClick={handleDelete}
            className="w-7 h-7 bg-white border border-gray-200 rounded-lg flex items-center justify-center text-gray-400 hover:text-red-500 hover:border-red-200 shadow-sm transition"
            title="Delete room"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}

export function RoomGrid({ rooms: initialRooms }: { rooms: Room[] }) {
  const [rooms, setRooms] = useState(initialRooms)

  function handleDeleted(id: string) {
    setRooms((prev) => prev.filter((r) => r.id !== id))
  }

  if (rooms.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-lg mb-2">No rooms yet</p>
        <p className="text-sm">Add a room to start mapping your home.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
      {rooms.map((room) => (
        <RoomCard key={room.id} room={room} onDeleted={handleDeleted} />
      ))}
    </div>
  )
}
