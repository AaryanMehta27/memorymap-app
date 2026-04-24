'use client'

import { useEffect, useRef, useState } from 'react'

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
  roomShape?: string
  roomWidth?: number
  roomHeight?: number
}

interface Popover {
  tag: Tag
  x: number
  y: number
}

// Emoji icon for common item types
function getItemEmoji(label: string): string {
  const l = label.toLowerCase()
  if (l.includes('pill') || l.includes('medicine') || l.includes('tablet') || l.includes('drug')) return '💊'
  if (l.includes('glass') || l.includes('spectacle')) return '👓'
  if (l.includes('phone') || l.includes('mobile') || l.includes('cell')) return '📱'
  if (l.includes('remote') || l.includes('control')) return '📺'
  if (l.includes('key')) return '🔑'
  if (l.includes('wallet') || l.includes('purse')) return '👜'
  if (l.includes('book') || l.includes('magazine')) return '📖'
  if (l.includes('lamp') || l.includes('light')) return '💡'
  if (l.includes('chair')) return '🪑'
  if (l.includes('bed') || l.includes('pillow')) return '🛏'
  if (l.includes('drawer') || l.includes('cabinet') || l.includes('wardrobe')) return '🗄'
  if (l.includes('table') || l.includes('desk')) return '🪵'
  if (l.includes('cup') || l.includes('mug') || l.includes('glass')) return '☕'
  if (l.includes('bag') || l.includes('handbag')) return '👜'
  if (l.includes('shoe') || l.includes('slipper')) return '👟'
  if (l.includes('tv') || l.includes('television') || l.includes('screen')) return '📺'
  if (l.includes('charger') || l.includes('cable')) return '🔌'
  if (l.includes('plant') || l.includes('flower')) return '🌿'
  if (l.includes('window')) return '🪟'
  if (l.includes('door')) return '🚪'
  if (l.includes('mirror')) return '🪞'
  if (l.includes('clock') || l.includes('watch')) return '🕐'
  return '📦'
}

function confidenceColor(confidence: string) {
  switch (confidence) {
    case 'high':   return { fill: '#16a34a', shadow: 'rgba(22,163,74,0.35)', label: 'text-green-700 bg-green-100' }
    case 'medium': return { fill: '#d97706', shadow: 'rgba(217,119,6,0.35)', label: 'text-amber-700 bg-amber-100' }
    default:       return { fill: '#dc2626', shadow: 'rgba(220,38,38,0.35)', label: 'text-red-700 bg-red-100' }
  }
}

// Spread overlapping tags so labels don't pile on top of each other
function spreadTags(tags: Tag[], minDist = 52): Tag[] {
  const placed = tags.map(t => ({ ...t }))
  const ITER = 30
  for (let iter = 0; iter < ITER; iter++) {
    for (let i = 0; i < placed.length; i++) {
      for (let j = i + 1; j < placed.length; j++) {
        const dx = (placed[i].canvas_x ?? 0) - (placed[j].canvas_x ?? 0)
        const dy = (placed[i].canvas_y ?? 0) - (placed[j].canvas_y ?? 0)
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < minDist && dist > 0) {
          const push = (minDist - dist) / 2
          const nx = dx / dist
          const ny = dy / dist
          placed[i] = { ...placed[i], canvas_x: (placed[i].canvas_x ?? 0) + nx * push, canvas_y: (placed[i].canvas_y ?? 0) + ny * push }
          placed[j] = { ...placed[j], canvas_x: (placed[j].canvas_x ?? 0) - nx * push, canvas_y: (placed[j].canvas_y ?? 0) - ny * push }
        }
      }
    }
  }
  return placed
}

export function FloorPlanCanvas({
  tags,
  photos,
  onPositionUpdate,
  roomId,
  roomShape = 'rectangle',
  roomWidth = 600,
  roomHeight = 400,
}: Props) {
  const [positionedTags, setPositionedTags] = useState<Tag[]>([])
  const [popover, setPopover] = useState<Popover | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const [KonvaComponents, setKonvaComponents] = useState<{
    Stage: React.ComponentType<unknown>
    Layer: React.ComponentType<unknown>
    Rect: React.ComponentType<unknown>
    Line: React.ComponentType<unknown>
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
        Line: mod.Line,
        Circle: mod.Circle,
        Text: mod.Text,
        Group: mod.Group,
      })
    })
  }, [])

  useEffect(() => {
    // Assign positions immediately using a smart grid — no AI call needed.
    // Once the user drags a tag, the new position is saved to Supabase and
    // used on subsequent loads (canvas_x / canvas_y will be non-null).
    const cols = Math.max(2, Math.ceil(Math.sqrt(tags.length)))
    const padX = Math.round(roomWidth * 0.12)
    const padY = Math.round(roomHeight * 0.14)
    const stepX = (roomWidth  - padX * 2) / Math.max(cols - 1, 1)
    const stepY = (roomHeight - padY * 2) / Math.max(Math.ceil(tags.length / cols) - 1, 1)

    const placed = tags.map((t, i) => ({
      ...t,
      canvas_x: t.canvas_x ?? padX + (i % cols) * stepX,
      canvas_y: t.canvas_y ?? padY + Math.floor(i / cols) * stepY,
    }))
    setPositionedTags(spreadTags(placed))
  }, [tags, roomWidth, roomHeight])

  if (!KonvaComponents) {
    return <div className="h-40 flex items-center justify-center text-sm text-gray-400">Loading canvas...</div>
  }

  const { Stage, Layer, Rect, Line, Circle, Text, Group } = KonvaComponents
  const photoForTag = (photoId: string) => photos.find((p) => p.id === photoId)

  // Grid line positions
  const gridSpacing = 60
  const gridLines: { x1: number; y1: number; x2: number; y2: number }[] = []
  for (let x = gridSpacing; x < roomWidth; x += gridSpacing) {
    gridLines.push({ x1: x, y1: 0, x2: x, y2: roomHeight })
  }
  for (let y = gridSpacing; y < roomHeight; y += gridSpacing) {
    gridLines.push({ x1: 0, y1: y, x2: roomWidth, y2: y })
  }

  // L-shape cut-out clip (top-right quadrant removed)
  const lCutX = Math.round(roomWidth * 0.55)
  const lCutY = Math.round(roomHeight * 0.45)

  // Compass labels
  const compassLabels = [
    { text: 'N', x: roomWidth / 2 - 5, y: 6 },
    { text: 'S', x: roomWidth / 2 - 5, y: roomHeight - 18 },
    { text: 'W', x: 6, y: roomHeight / 2 - 7 },
    { text: 'E', x: roomWidth - 14, y: roomHeight / 2 - 7 },
  ]

  return (
    <div className="space-y-2">
      <div ref={containerRef} className="relative border border-gray-200 rounded-xl overflow-hidden bg-white inline-block shadow-sm">
        {/* @ts-expect-error konva types */}
        <Stage width={roomWidth} height={roomHeight}>
          {/* @ts-expect-error konva types */}
          <Layer>
            {/* Room fill */}
            {/* @ts-expect-error konva types */}
            <Rect x={0} y={0} width={roomWidth} height={roomHeight} fill="#f8fafc" />

            {/* Grid lines */}
            {gridLines.map((l, i) => (
              // @ts-expect-error konva types
              <Line key={i} points={[l.x1, l.y1, l.x2, l.y2]} stroke="#e2e8f0" strokeWidth={1} />
            ))}

            {/* L-shape cut-out (grey overlay on the missing quadrant) */}
            {roomShape === 'l-shape' && (
              // @ts-expect-error konva types
              <Rect x={lCutX} y={0} width={roomWidth - lCutX} height={lCutY} fill="#e9ecef" cornerRadius={4} />
            )}

            {/* Narrow room — centre stripe */}
            {roomShape === 'narrow' && (
              // @ts-expect-error konva types
              <Rect x={0} y={roomHeight * 0.3} width={roomWidth} height={roomHeight * 0.4} fill="#f1f5f9" />
            )}

            {/* Room border */}
            {/* @ts-expect-error konva types */}
            <Rect x={4} y={4} width={roomWidth - 8} height={roomHeight - 8} stroke="#cbd5e1" strokeWidth={1.5} fill="transparent" cornerRadius={6} />

            {/* Compass labels */}
            {compassLabels.map((c) => (
              // @ts-expect-error konva types
              <Text key={c.text} text={c.text} x={c.x} y={c.y} fontSize={10} fill="#94a3b8" fontStyle="bold" />
            ))}

            {/* Tags */}
            {positionedTags.map((tag) => {
              const x = Math.max(24, Math.min(roomWidth - 24, tag.canvas_x ?? 100))
              const y = Math.max(24, Math.min(roomHeight - 24, tag.canvas_y ?? 100))
              const colors = confidenceColor(tag.confidence)
              const emoji = getItemEmoji(tag.label)

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
                  {/* Outer glow ring */}
                  {/* @ts-expect-error konva types */}
                  <Circle radius={22} fill={colors.shadow} />
                  {/* Main dot */}
                  {/* @ts-expect-error konva types */}
                  <Circle radius={17} fill={colors.fill} shadowBlur={6} shadowColor={colors.shadow} />
                  {/* Emoji icon */}
                  {/* @ts-expect-error konva types */}
                  <Text
                    text={emoji}
                    fontSize={14}
                    x={-9}
                    y={-9}
                  />
                  {/* Label below dot */}
                  {/* @ts-expect-error konva types */}
                  <Text
                    text={tag.label.length > 14 ? tag.label.slice(0, 13) + '…' : tag.label}
                    fontSize={9}
                    fill="#1e293b"
                    fontStyle="bold"
                    x={-36}
                    y={24}
                    width={72}
                    align="center"
                  />
                </Group>
              )
            })}
          {/* @ts-expect-error konva types */}
          </Layer>
        {/* @ts-expect-error konva types */}
        </Stage>

        {/* Click popover */}
        {popover && (
          <div
            className="absolute z-10 bg-white border border-gray-200 rounded-xl shadow-xl p-3 w-52 text-sm"
            style={{
              left: Math.min(popover.x + 24, roomWidth - 216),
              top: Math.min(popover.y - 10, roomHeight - 160),
            }}
          >
            <button
              className="absolute top-2 right-2 text-gray-300 hover:text-gray-500 text-xs"
              onClick={() => setPopover(null)}
            >✕</button>
            <p className="font-semibold text-gray-800 pr-4 leading-tight">{popover.tag.label}</p>
            <p className="text-gray-500 text-xs mt-1">{popover.tag.position}</p>
            {popover.tag.notes && <p className="text-gray-400 text-xs mt-1 italic">{popover.tag.notes}</p>}
            <span className={`inline-block mt-2 text-xs rounded-full px-2 py-0.5 font-medium ${confidenceColor(popover.tag.confidence).label}`}>
              {popover.tag.confidence} confidence
            </span>
            {photoForTag(popover.tag.photo_id)?.signedUrl && (
              <img
                src={photoForTag(popover.tag.photo_id)!.signedUrl}
                alt={popover.tag.label}
                className="w-full rounded-lg mt-2 object-cover max-h-24"
              />
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-gray-500 px-1">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />High confidence</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />Medium</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />Low / stale</span>
        <span className="ml-auto text-gray-400 italic">Drag dots to reposition</span>
      </div>
    </div>
  )
}
