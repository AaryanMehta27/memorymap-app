'use client'

import { useRef, useState, useEffect, useCallback } from 'react'
import { PrivacyConsentModal } from './PrivacyConsentModal'
import { createClient } from '@/lib/supabase/client'

interface Props {
  roomId: string
  userId: string
  onCaptureDone: (photoId: string, storagePath: string) => void
  onClose: () => void
}

type Step = 'consent' | 'camera' | 'uploading'

export function CameraCapture({ roomId, userId, onCaptureDone, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [step, setStep] = useState<Step>('consent')
  const [error, setError] = useState('')

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  useEffect(() => {
    return () => stopStream()
  }, [stopStream])

  async function startCamera() {
    setStep('camera')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }
    } catch {
      setError('Could not access camera. Please check permissions.')
    }
  }

  async function captureFrame() {
    if (!videoRef.current || !canvasRef.current) return
    const video = videoRef.current
    const canvas = canvasRef.current
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d')?.drawImage(video, 0, 0)

    stopStream() // Stop stream immediately after capture

    setStep('uploading')

    canvas.toBlob(async (blob) => {
      if (!blob) { setError('Failed to capture image.'); return }

      const supabase = createClient()
      const photoId = crypto.randomUUID()
      const storagePath = `${userId}/${roomId}/${photoId}.jpg`

      const { error: uploadError } = await supabase.storage
        .from('photos')
        .upload(storagePath, blob, { contentType: 'image/jpeg' })

      if (uploadError) { setError(uploadError.message); return }

      const { error: dbError } = await supabase
        .from('photos')
        .insert({ id: photoId, room_id: roomId, storage_path: storagePath })

      if (dbError) { setError(dbError.message); return }

      onCaptureDone(photoId, storagePath)
    }, 'image/jpeg', 0.85)
  }

  function handleCancel() {
    stopStream()
    onClose()
  }

  return (
    <>
      {step === 'consent' && (
        <PrivacyConsentModal onAccept={startCamera} onCancel={handleCancel} />
      )}

      {(step === 'camera' || step === 'uploading') && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full max-w-lg rounded-lg"
          />
          <canvas ref={canvasRef} className="hidden" />

          {error && (
            <p className="text-red-400 text-sm mt-3">{error}</p>
          )}

          <div className="flex gap-4 mt-5">
            <button
              onClick={handleCancel}
              className="border border-white/30 text-white rounded-lg px-5 py-2 text-sm hover:bg-white/10 transition"
            >
              Cancel
            </button>
            {step === 'camera' && (
              <button
                onClick={captureFrame}
                className="bg-white text-gray-900 font-medium rounded-lg px-6 py-2 text-sm hover:bg-gray-100 transition"
              >
                Capture
              </button>
            )}
            {step === 'uploading' && (
              <span className="text-white/70 text-sm py-2">Uploading...</span>
            )}
          </div>
        </div>
      )}
    </>
  )
}
