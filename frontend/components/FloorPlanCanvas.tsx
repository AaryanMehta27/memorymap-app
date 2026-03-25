'use client'

import { useEffect, useRef, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { suggestFloorPlanPositions } from '@/lib/ai-client'

interface Tag {
  id: string
  photo_id: string
  label: string
  position: string
  confidence: string
  notes: string | null
  canvas_x: number | null
  canvas_y: number | null
}

interface Photo {
  id: string
  signedUrl?: string
}

interface Props {
  tags: Tag[]
  photos: Photo[]
  onPositionUpdate: (tagId: string, x: number, y: number) => void
  roomId: string
  roomWidth?: number
  roomHeight?: number
}

interface Popover {
  tag: Tag
  x: number
  y: number
}

export function FloorPlanCanvas({
  tags,
  photos,
  onPositionUpdate,
  roomId,
  roomWidth = 600,
  roomHeight = 400,
}: Props) {
  const [positionedTags, setPositionedTags] = useState<Tag[]>([])
  const [popover, setPopover] = useState<Popover | null>(null)
  const [loadingPositions, setLoadingPositions] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Konva is client-only — load dynamically
  const [KonvaComponents, setKonvaComponents] = useState<{
    Stage: React.ComponentType<unknown>
    Layer: React.ComponentType<unknown>
    Rect: React.ComponentType<unknown>
    Circle: React.ComponentType<unknown>
    Text: React.ComponentType<unknown>
    Group: React.ComponentType<unknown>
  } | null>(null)

  useEffect(() => {
    import('react-konva').then((mod) => {
      setKonvaComponents({
        Stage: mod.Stage,
        Layer: mod.Layer,
        Rect: mod.Rect,
        Circle: mod.Circle,
        Text: mod.Text,
        Group: mod.Group,
      })
    })
  }, [])

  useEffect(() => {
    async function resolvePositions() {
      const needsPosition = tags.filter((t) => t.canvas_x == null || t.canvas_y == null)
      if (needsPosition.length === 0) {
        setPositionedTags(tags)
        return
      }

      setLoadingPositions(true)
      try {
        const supabase = createClient()
        const { data: { session } } = await supabase.auth.getSession()
        const token = session?.access_token ?? ''

        const result = await suggestFloorPlanPositions(
          roomId, needsPosition, roomWidth, roomHeight, token
        )

        const updated = tags.map((t) => {
          const suggested = result.positions?.find((p: { tag_id: string; canvas_x: number; canvas_y: number }) => p.tag_id === t.id)
          if (suggested) {
            onPositionUpdate(t.id, suggested.canvas_x, suggested.canvas_y)
            return { ...t, canvas_x: suggested.canvas_x, canvas_y: suggested.canvas_y }
          }
          return t
        })
        setPositionedTags(updated)
      } catch {
        // Fall back to a simple grid layout
        const cols = Math.ceil(Math.sqrt(tags.length))
        const fallback = tags.map((t, i) => ({
          ...t,
          canvas_x: t.canvas_x ?? 60 + (i % cols) * (roomWidth / (cols + 1)),
          canvas_y: t.canvas_y ?? 60 + Math.floor(i / cols) * (roomHeight / (cols + 1)),
        }))
        setPositionedTags(fallback)
      } finally {
        setLoadingPositions(false)
      }
    }
    resolvePositions()
  }, [tags, roomId, roomWidth, roomHeight])

  if (!KonvaComponents) {
    return <div className="h-40 flex items-center justify-center text-sm text-gray-400">Loading canvas...</div>
  }

  if (loadingPositions) {
    return <div className="h-40 flex items-center justify-center text-sm text-gray-400">Placing tags on floor plan...</div>
  }

  const { Stage, Layer, Rect, Circle, Text, Group } = KonvaComponents

  const photoForTag = (photoId: string) => photos.find((p) => p.id === photoId)

  return (
    <div ref={containerRef} className="relative border border-gray-200 rounded-xl overflow-hidden bg-white inline-block">
      {/* @ts-expect-error konva types */}
      <Stage width={roomWidth} height={roomHeight}>
        {/* @ts-expect-error konva types */}
        <Layer>
          {/* Room background */}
          {/* @ts-expect-error konva types */}
          <Rect x={0} y={0} width={roomWidth} height={roomHeight} fill="#f8fafc" />
          {/* Room border */}
          {/* @ts-expect-error konva types */}
          <Rect x={4} y={4} width={roomWidth - 8} height={roomHeight - 8} stroke="#e2e8f0" strokeWidth={2} fill="transparent" cornerRadius={8} />

          {positionedTags.map((tag) => {
            const x = tag.canvas_x ?? 100
            const y = tag.canvas_y ?? 100
            return (
              // @ts-expect-error konva types
              <Group
                key={tag.id}
                x={x}
                y={y}
                draggable
                onDragEnd={(e: { target: { x: () => number; y: () => number } }) => {
                  onPositionUpdate(tag.id, e.target.x(), e.target.y())
                }}
                onClick={() => setPopover(popover?.tag.id === tag.id ? null : { tag, x, y })}
                onTap={() => setPopover(popover?.tag.id === tag.id ? null : { tag, x, y })}
              >
                {/* @ts-expect-error konva types */}
                <Circle radius={18} fill="#4F46E5" shadowBlur={4} shadowColor="rgba(79,70,229,0.3)" />
                {/* @ts-expect-error konva types */}
                <Text
                  text={tag.label}
                  fontSize={10}
                  fill="#1e293b"
                  x={-40}
                  y={22}
                  width={80}
                  align="center"
                />
              </Group>
            )
          })}
        {/* @ts-expect-error konva types */}
        </Layer>
      {/* @ts-expect-error konva types */}
      </Stage>

      {/* Popover overlay (HTML, not Konva) */}
      {popover && (
        <div
          className="absolute z-10 bg-white border border-gray-200 rounded-xl shadow-lg p-3 w-48 text-sm"
          style={{
            left: Math.min(popover.x + 20, roomWidth - 200),
            top: Math.min(popover.y - 10, roomHeight - 140),
          }}
        >
          <button
            className="absolute top-2 right-2 text-gray-300 hover:text-gray-500 text-xs"
            onClick={() => setPopover(null)}
          >✕</button>
          <p className="font-semibold text-gray-800 pr-4">{popover.tag.label}</p>
          <p className="text-gray-500 text-xs mt-0.5">{popover.tag.position}</p>
          {popover.tag.notes && <p className="text-gray-400 text-xs mt-1">{popover.tag.notes}</p>}
          {photoForTag(popover.tag.photo_id)?.signedUrl && (
            <img
              src={photoForTag(popover.tag.photo_id)!.signedUrl}
              alt={popover.tag.label}
              className="w-full rounded-lg mt-2 object-cover max-h-20"
            />
          )}
        </div>
      )}
    </div>
  )
}
