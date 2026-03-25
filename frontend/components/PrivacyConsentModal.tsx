'use client'

interface Props {
  onAccept: () => void
  onCancel: () => void
}

export function PrivacyConsentModal({ onAccept, onCancel }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Before using the camera</h2>

        <ul className="space-y-2 text-sm text-gray-600 mb-5">
          <li className="flex gap-2">
            <span className="text-indigo-500 mt-0.5">•</span>
            <span>Your camera is used to photograph rooms and objects in your home for mapping purposes.</span>
          </li>
          <li className="flex gap-2">
            <span className="text-indigo-500 mt-0.5">•</span>
            <span>Captured images are sent to <strong>Google Gemini API</strong> for AI object detection analysis.</span>
          </li>
          <li className="flex gap-2">
            <span className="text-indigo-500 mt-0.5">•</span>
            <span>Google's standard API data usage policies apply to images sent for analysis.</span>
          </li>
          <li className="flex gap-2">
            <span className="text-indigo-500 mt-0.5">•</span>
            <span>MemoryMap does <strong>not</strong> store images on its own servers. Images are processed in-memory only.</span>
          </li>
        </ul>

        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-50 transition"
          >
            Cancel
          </button>
          <button
            onClick={onAccept}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg py-2 text-sm font-medium transition"
          >
            I understand, continue
          </button>
        </div>
      </div>
    </div>
  )
}
