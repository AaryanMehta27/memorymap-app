'use client'

import { useEffect, useState, useCallback, use } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { CameraCapture } from '@/components/CameraCapture'
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
  const [importantItems, setImportantItems] = useState<string[]>([])
  const [photos, setPhotos] = useState<Photo[]>([])
  const [tags, setTags] = useState<Tag[]>([])
  const [userId, setUserId] = useState<string>('')
  const [role, setRole] = useState<string>('caregiver')
  const [showCamera, setShowCamera] = useState(false)
  const [analyzingPhotoId, setAnalyzingPhotoId] = useState<string | null>(null)
  const [deletingPhotoId, setDeletingPhotoId] = useState<string | null>(null)
  const [confirmDeletePhotoId, setConfirmDeletePhotoId] = useState<string | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [error, setError] = useState('')

  const [showSimulate, setShowSimulate] = useState(false)
  const [simulateText, setSimulateText] = useState('')
  const [simulatingSaving, setSimulatingSaving] = useState(false)
  const [deletingTagId, setDeletingTagId] = useState<string | null>(null)

  const supabase = createClient()

  const loadData = useCallback(async () => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) { router.push('/auth/login'); return }
    setUserId(user.id)

    const { data: roleRow } = await supabase
      .from('user_roles').select('role').eq('user_id', user.id).single()
    setRole(roleRow?.role ?? 'caregiver')

    const { data: roomData } = await supabase
      .from('rooms').select('name, shape, home_id').eq('id', room_id).single()
    if (roomData) {
      setRoom({ name: roomData.name, shape: roomData.shape })
      if (roomData.home_id) {
        const { data: homeRow } = await supabase
          .from('homes').select('important_items').eq('id', roomData.home_id).single()
        setImportantItems(homeRow?.important_items ?? [])
      }
    }

    const { data: photoData } = await supabase
      .from('photos').select('*').eq('room_id', room_id).order('captured_at', { ascending: false })

    if (photoData) {
      const withUrls = await Promise.all(
        photoData.map(async (p) => {
          if (p.storage_path.startsWith('simulated/')) return { ...p, signedUrl: undefined }
          const { data } = await supabase.storage.from('photos').createSignedUrl(p.storage_path, 3600)
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

      const result = await analyzePhoto(room_id, base64, blob.type, token, importantItems)

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
      const msg = err instanceof Error ? err.message : 'Analysis failed.'
      setError(msg.includes('abort') ? 'Analysis timed out — try again in a moment.' : msg)
    } finally {
      setAnalyzingPhotoId(null)
    }
  }

  async function handleSimulate() {
    if (!simulateText.trim()) return
    setSimulatingSaving(true)
    setError('')
    try {
      const lines = simulateText.trim().split('\n').filter(l => l.trim())
      const parsedTags = lines.map(line => {
        const parts = line.split(',').map(s => s.trim())
        return {
          label: parts[0] ?? 'unknown item',
          position: parts[1] ?? 'unknown',
          confidence: (['high', 'medium', 'low'].includes(parts[2]?.toLowerCase()) ? parts[2].toLowerCase() : 'medium'),
          notes: parts[3] ?? '',
        }
      })

      const photoId = crypto.randomUUID()
      await supabase.from('photos').insert({
        id: photoId,
        room_id,
        storage_path: `simulated/${photoId}`,
      })

      await supabase.from('tags').insert(
        parsedTags.map(t => ({
          photo_id: photoId,
          room_id,
          label: t.label,
          position: t.position,
          confidence: t.confidence,
          notes: t.notes || null,
        }))
      )
      setSimulateText('')
      setShowSimulate(false)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save.')
    } finally {
      setSimulatingSaving(false)
    }
  }

  async function handleDeletePhoto(photo: Photo) {
    if (!photo.storage_path.startsWith('simulated/')) {
      await supabase.storage.from('photos').remove([photo.storage_path])
    }
    await supabase.from('tags').delete().eq('photo_id', photo.id)
    await supabase.from('photos').delete().eq('id', photo.id)
    loadData()
  }

  async function handleDeleteTag(tagId: string) {
    setDeletingTagId(tagId)
    await supabase.from('tags').delete().eq('id', tagId)
    setTags(prev => prev.filter(t => t.id !== tagId))
    setDeletingTagId(null)
  }

  async function handleTagUpdate(tagId: string, label: string, notes: string) {
    await supabase.from('tags').update({ label, notes }).eq('id', tagId)
    setTags(prev => prev.map(t => t.id === tagId ? { ...t, label, notes } : t))
  }

  const simulatedPhotoIds = new Set(photos.filter(p => p.storage_path.startsWith('simulated/')).map(p => p.id))
  const manualTags = tags.filter(t => simulatedPhotoIds.has(t.photo_id))
  const realPhotos = photos.filter(p => !p.storage_path.startsWith('simulated/'))

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
      </div>

      <div className="mb-5">
          <button
            onClick={() => setShowSimulate(v => !v)}
            className="bg-white border border-gray-300 text-gray-700 text-sm font-medium rounded-lg px-4 py-2 hover:bg-gray-50 transition flex items-center gap-2"
          >
            <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            {showSimulate ? 'Hide text entry' : 'Enter room data manually'}
          </button>

          {showSimulate && (
            <div className="mt-3 bg-indigo-50 border border-indigo-200 rounded-xl p-4 space-y-3">
              <div>
                <p className="text-sm font-medium text-indigo-900 mb-1">Enter items — one per line:</p>
                <p className="text-xs text-indigo-600 mb-2">Format: <code className="bg-indigo-100 px-1 rounded">label, position, confidence (high/medium/low), notes</code></p>
                <textarea
                  value={simulateText}
                  onChange={e => setSimulateText(e.target.value)}
                  rows={6}
                  placeholder={"reading glasses, nightstand surface, high, black wire frames\nmedicine bottle, kitchen counter left, high, orange prescription bottle\nkeys, hook near front door, medium, house and car keys\nTV remote, couch right cushion, medium, black remote\nwallet, bedroom dresser top, high, brown leather wallet\nhearing aid, bathroom shelf, high, small beige device in case"}
                  className="w-full border border-indigo-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
                />
              </div>

              <div className="flex flex-wrap gap-2">
                <p className="text-xs text-indigo-700 font-medium w-full">Sample presets:</p>
                {[
                  {
                    label: 'Bedroom',
                    text: 'reading glasses, nightstand surface, high, black wire frames\nmedicine bottle, bedside drawer top, high, orange prescription bottle\nhearing aid, nightstand left side, high, small beige device in charging case\nwater cup, nightstand right side, medium, clear glass with lid\nphone charger, outlet near bed, medium, white cable plugged in',
                  },
                  {
                    label: 'Kitchen',
                    text: 'medicine, kitchen counter left, high, daily pill organizer blue\nkeys, hook by back door, high, house and car keys on ring\nglasses case, kitchen table, medium, hard black case\nreceipts, kitchen counter right, low, loose papers near microwave\nphone, kitchen island, medium, on wireless charging pad',
                  },
                  {
                    label: 'Living room',
                    text: 'TV remote, couch right cushion, medium, black remote control\nreading glasses, coffee table, high, gold frame glasses\nblood pressure monitor, side table, high, white cuff device in case\nmagazines, coffee table bottom shelf, low, stack of reading material\nphone, armchair side table, medium, in protective case',
                  },
                ].map(preset => (
                  <button
                    key={preset.label}
                    onClick={() => setSimulateText(preset.text)}
                    className="text-xs bg-white border border-indigo-300 text-indigo-700 rounded-lg px-3 py-1.5 hover:bg-indigo-100 transition"
                  >
                    Use {preset.label} sample
                  </button>
                ))}
              </div>

              <button
                onClick={handleSimulate}
                disabled={simulatingSaving || !simulateText.trim()}
                className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition disabled:opacity-50"
              >
                {simulatingSaving ? 'Saving...' : 'Save tags'}
              </button>
            </div>
          )}
        </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">{error}</p>
      )}

      {manualTags.length > 0 && (
        <div className="mb-8">
          <h2 className="text-base font-medium text-gray-800 mb-3">Tagged items</h2>
          <div className="space-y-2">
            {manualTags.map(tag => (
              <TagRow
                key={tag.id}
                tag={tag}
                editable={true}
                deleting={deletingTagId === tag.id}
                onUpdate={handleTagUpdate}
                onDelete={handleDeleteTag}
              />
            ))}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-base font-medium text-gray-800 mb-3">Photos</h2>
        {realPhotos.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No photos yet. Upload or capture one above.</p>
        ) : (
          <div className="space-y-6">
            {realPhotos.map((photo) => {
              const photoTags = tags.filter(t => t.photo_id === photo.id)
              return (
                <div key={photo.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                  {photo.signedUrl && (
                    <img src={photo.signedUrl} alt="Room photo" className="w-full object-cover max-h-64" />
                  )}
                  <div className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <button
                          onClick={() => handleAnalyze(photo)}
                          disabled={analyzingPhotoId === photo.id}
                          className="text-sm bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-medium rounded-lg px-4 py-1.5 transition disabled:opacity-50"
                        >
                          {analyzingPhotoId === photo.id ? 'Analysing...' : 'Analyse photo'}
                        </button>

                        {confirmDeletePhotoId === photo.id ? (
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs text-red-600 font-medium">Delete photo + tags?</span>
                            <button
                              onClick={async () => {
                                setDeletingPhotoId(photo.id)
                                await handleDeletePhoto(photo)
                                setDeletingPhotoId(null)
                                setConfirmDeletePhotoId(null)
                              }}
                              disabled={deletingPhotoId === photo.id}
                              className="text-xs bg-red-500 hover:bg-red-600 text-white rounded px-2 py-1 font-medium disabled:opacity-50"
                            >
                              {deletingPhotoId === photo.id ? '...' : 'Yes, delete'}
                            </button>
                            <button onClick={() => setConfirmDeletePhotoId(null)} className="text-xs text-gray-400 hover:text-gray-600">Cancel</button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setConfirmDeletePhotoId(photo.id)}
                            className="text-sm text-gray-400 hover:text-red-500 transition px-2 py-1.5 rounded-lg hover:bg-red-50"
                            title="Delete photo"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        )}
                      </div>

                    {photoTags.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tags</p>
                        {photoTags.map(tag => (
                          <TagRow
                            key={tag.id}
                            tag={tag}
                            editable={true}
                            deleting={deletingTagId === tag.id}
                            onUpdate={handleTagUpdate}
                            onDelete={handleDeleteTag}
                          />
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

function TagRow({ tag, editable, deleting, onUpdate, onDelete }: {
  tag: Tag
  editable: boolean
  deleting: boolean
  onUpdate: (id: string, label: string, notes: string) => void
  onDelete: (id: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [label, setLabel] = useState(tag.label)
  const [notes, setNotes] = useState(tag.notes ?? '')
  const [confirmDelete, setConfirmDelete] = useState(false)

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
          onChange={e => setLabel(e.target.value)}
          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
        />
        <input
          value={notes}
          onChange={e => setNotes(e.target.value)}
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
        {editable && !confirmDelete && (
          <>
            <button onClick={() => setEditing(true)} className="text-xs text-gray-400 hover:text-indigo-600">Edit</button>
            <button onClick={() => setConfirmDelete(true)} className="text-xs text-gray-400 hover:text-red-500">Delete</button>
          </>
        )}
        {editable && confirmDelete && (
          <div className="flex items-center gap-1">
            <span className="text-xs text-red-600">Sure?</span>
            <button
              onClick={() => { onDelete(tag.id); setConfirmDelete(false) }}
              disabled={deleting}
              className="text-xs bg-red-500 text-white rounded px-2 py-0.5 disabled:opacity-50"
            >{deleting ? '...' : 'Yes'}</button>
            <button onClick={() => setConfirmDelete(false)} className="text-xs text-gray-400">No</button>
          </div>
        )}
      </div>
    </div>
  )
}
