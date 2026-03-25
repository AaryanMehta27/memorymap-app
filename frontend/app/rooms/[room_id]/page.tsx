'use client'

import { useEffect, useState, useCallback, use } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { CameraCapture } from '@/components/CameraCapture'
import { FloorPlanCanvas } from '@/components/FloorPlanCanvas'
import { analyzePhoto } from '@/lib/ai-client'

interface Photo {
  id: string
  storage_path: string
  captured_at: string
  signedUrl?: string
}

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

export default function RoomDetailPage({ params }: { params: Promise<{ room_id: string }> }) {
  const { room_id } = use(params)
  const router = useRouter()
  const [room, setRoom] = useState<{ name: string; shape: string } | null>(null)
  const [photos, setPhotos] = useState<Photo[]>([])
  const [tags, setTags] = useState<Tag[]>([])
  const [userId, setUserId] = useState<string>('')
  const [role, setRole] = useState<string>('caregiver')
  const [showCamera, setShowCamera] = useState(false)
  const [analyzingPhotoId, setAnalyzingPhotoId] = useState<string | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [error, setError] = useState('')

  const supabase = createClient()

  const loadData = useCallback(async () => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) { router.push('/auth/login'); return }
    setUserId(user.id)

    const { data: roleRow } = await supabase
      .from('user_roles').select('role').eq('user_id', user.id).single()
    setRole(roleRow?.role ?? 'caregiver')

    const { data: roomData } = await supabase
      .from('rooms').select('name, shape').eq('id', room_id).single()
    if (roomData) setRoom(roomData)

    const { data: photoData } = await supabase
      .from('photos').select('*').eq('room_id', room_id).order('captured_at', { ascending: false })

    if (photoData) {
      const withUrls = await Promise.all(
        photoData.map(async (p) => {
          const { data } = await supabase.storage
            .from('photos')
            .createSignedUrl(p.storage_path, 3600)
          return { ...p, signedUrl: data?.signedUrl }
        })
      )
      setPhotos(withUrls)
    }

    const { data: tagData } = await supabase
      .from('tags').select('*').eq('room_id', room_id).order('created_at', { ascending: true })
    if (tagData) setTags(tagData)
  }, [room_id, router])

  useEffect(() => { loadData() }, [loadData])

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingFile(true)
    setError('')

    const photoId = crypto.randomUUID()
    const storagePath = `${userId}/${room_id}/${photoId}.jpg`

    const { error: uploadError } = await supabase.storage
      .from('photos')
      .upload(storagePath, file, { contentType: file.type })

    if (uploadError) { setError(uploadError.message); setUploadingFile(false); return }

    await supabase.from('photos').insert({ id: photoId, room_id, storage_path: storagePath })
    setUploadingFile(false)
    loadData()
  }

  async function handleAnalyze(photo: Photo) {
    if (!photo.signedUrl) return
    setAnalyzingPhotoId(photo.id)
    setError('')

    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token ?? ''

      const imgRes = await fetch(photo.signedUrl)
      const blob = await imgRes.blob()
      const base64 = await new Promise<string>((resolve) => {
        const reader = new FileReader()
        reader.onloadend = () => resolve((reader.result as string).split(',')[1])
        reader.readAsDataURL(blob)
      })

      const result = await analyzePhoto(room_id, base64, blob.type, token)

      if (result.tags?.length) {
        await supabase.from('tags').insert(
          result.tags.map((t: Omit<Tag, 'id' | 'photo_id'>) => ({
            photo_id: photo.id,
            room_id,
            label: t.label,
            position: t.position,
            confidence: t.confidence,
            notes: t.notes ?? null,
            canvas_x: (t as Tag).canvas_x ?? null,
            canvas_y: (t as Tag).canvas_y ?? null,
          }))
        )
        await loadData()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed.')
    } finally {
      setAnalyzingPhotoId(null)
    }
  }

  async function handleTagUpdate(tagId: string, label: string, notes: string) {
    await supabase.from('tags').update({ label, notes }).eq('id', tagId)
    setTags((prev) => prev.map((t) => t.id === tagId ? { ...t, label, notes } : t))
  }

  async function handleTagPositionUpdate(tagId: string, x: number, y: number) {
    await supabase.from('tags').update({ canvas_x: x, canvas_y: y }).eq('id', tagId)
    setTags((prev) => prev.map((t) => t.id === tagId ? { ...t, canvas_x: x, canvas_y: y } : t))
  }

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <button onClick={() => router.push('/dashboard')} className="text-sm text-gray-500 hover:text-gray-700 mb-5 flex items-center gap-1">
        ← Dashboard
      </button>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{room?.name ?? '...'}</h1>
          <p className="text-sm text-gray-400 capitalize">{room?.shape}</p>
        </div>
        {role === 'caregiver' && (
          <div className="flex gap-2">
            <label className={`cursor-pointer bg-white border border-gray-300 text-gray-700 text-sm font-medium rounded-lg px-4 py-2 hover:bg-gray-50 transition ${uploadingFile ? 'opacity-50 pointer-events-none' : ''}`}>
              {uploadingFile ? 'Uploading...' : 'Upload photo'}
              <input type="file" accept="image/*" className="hidden" onChange={handleFileUpload} disabled={uploadingFile} />
            </label>
            <button
              onClick={() => setShowCamera(true)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition"
            >
              Capture from camera
            </button>
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">{error}</p>
      )}

      {tags.length > 0 && (
        <div className="mb-8">
          <h2 className="text-base font-medium text-gray-800 mb-3">Floor plan</h2>
          <FloorPlanCanvas
            tags={tags}
            photos={photos}
            onPositionUpdate={handleTagPositionUpdate}
            roomId={room_id}
          />
        </div>
      )}

      <div>
        <h2 className="text-base font-medium text-gray-800 mb-3">Photos</h2>
        {photos.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No photos yet. Upload or capture one above.</p>
        ) : (
          <div className="space-y-6">
            {photos.map((photo) => {
              const photoTags = tags.filter((t) => t.photo_id === photo.id)
              return (
                <div key={photo.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                  {photo.signedUrl && (
                    <img src={photo.signedUrl} alt="Room photo" className="w-full object-cover max-h-64" />
                  )}
                  <div className="p-4">
                    {role === 'caregiver' && (
                      <button
                        onClick={() => handleAnalyze(photo)}
                        disabled={analyzingPhotoId === photo.id}
                        className="text-sm bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-medium rounded-lg px-4 py-1.5 transition disabled:opacity-50 mb-3"
                      >
                        {analyzingPhotoId === photo.id ? 'Analysing...' : 'Analyse photo'}
                      </button>
                    )}

                    {photoTags.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tags</p>
                        {photoTags.map((tag) => (
                          <TagRow key={tag.id} tag={tag} editable={role === 'caregiver'} onUpdate={handleTagUpdate} />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {showCamera && userId && (
        <CameraCapture
          roomId={room_id}
          userId={userId}
          onCaptureDone={() => { setShowCamera(false); loadData() }}
          onClose={() => setShowCamera(false)}
        />
      )}
    </main>
  )
}

function TagRow({ tag, editable, onUpdate }: {
  tag: Tag
  editable: boolean
  onUpdate: (id: string, label: string, notes: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [label, setLabel] = useState(tag.label)
  const [notes, setNotes] = useState(tag.notes ?? '')

  const confidenceColor: Record<string, string> = {
    high: 'bg-green-100 text-green-700',
    medium: 'bg-yellow-100 text-yellow-700',
    low: 'bg-red-100 text-red-700',
  }

  if (editing) {
    return (
      <div className="border border-indigo-200 rounded-lg p-3 bg-indigo-50 space-y-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
        />
        <input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notes (optional)"
          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
        />
        <div className="flex gap-2">
          <button
            onClick={() => { onUpdate(tag.id, label, notes); setEditing(false) }}
            className="text-xs bg-indigo-600 text-white rounded px-3 py-1"
          >Save</button>
          <button onClick={() => setEditing(false)} className="text-xs text-gray-500">Cancel</button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start justify-between gap-2 text-sm border border-gray-100 rounded-lg px-3 py-2">
      <div>
        <span className="font-medium text-gray-800">{tag.label}</span>
        <span className="text-gray-400 mx-1">·</span>
        <span className="text-gray-500">{tag.position}</span>
        {tag.notes && <p className="text-xs text-gray-400 mt-0.5">{tag.notes}</p>}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${confidenceColor[tag.confidence] ?? ''}`}>
          {tag.confidence}
        </span>
        {editable && (
          <button onClick={() => setEditing(true)} className="text-xs text-gray-400 hover:text-indigo-600">Edit</button>
        )}
      </div>
    </div>
  )
}
