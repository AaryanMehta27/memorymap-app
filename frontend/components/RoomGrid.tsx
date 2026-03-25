'use client'

import Link from 'next/link'

interface Room {
  id: string
  name: string
  shape: string
  photoCount: number
  tagCount: number
}

export function RoomGrid({ rooms }: { rooms: Room[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
      {rooms.map((room) => (
        <Link
          key={room.id}
          href={`/rooms/${room.id}`}
          className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md hover:border-indigo-300 transition group"
        >
          <div className="flex items-start justify-between mb-3">
            <div className="w-10 h-10 bg-indigo-50 rounded-lg flex items-center justify-center text-indigo-600 text-xl">
              {room.shape === 'l-shape' ? '⌐' : '▭'}
            </div>
            <span className="text-xs text-gray-400 capitalize">{room.shape}</span>
          </div>
          <h3 className="font-medium text-gray-900 group-hover:text-indigo-600 transition">{room.name}</h3>
          <p className="text-xs text-gray-400 mt-1">
            {room.photoCount} photo{room.photoCount !== 1 ? 's' : ''} · {room.tagCount} tag{room.tagCount !== 1 ? 's' : ''}
          </p>
        </Link>
      ))}
    </div>
  )
}
