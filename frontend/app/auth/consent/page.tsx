'use client'

import { useRouter } from 'next/navigation'

export default function ConsentPage() {
  const router = useRouter()

  function handleAccept() {
    router.push('/dashboard')
  }

  return (
    <div className="min-h-screen flex items-end sm:items-center justify-center bg-gray-50 px-4 pb-4 sm:pb-0">
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6 border border-gray-100">
        <div className="text-4xl mb-4 text-center">💙</div>
        <h2 className="text-xl font-semibold text-gray-900 text-center mb-4">
          Welcome to MemoryMap
        </h2>

        <ul className="space-y-3 text-sm text-gray-600 mb-6">
          <li className="flex gap-2 items-start">
            <span className="text-indigo-500 shrink-0 mt-0.5">•</span>
            <span>
              MemoryMap uses <strong>AI (Google Gemini)</strong> to analyse photos of your home and help you find your belongings.
            </span>
          </li>
          <li className="flex gap-2 items-start">
            <span className="text-indigo-500 shrink-0 mt-0.5">•</span>
            <span>
              Photos you take are sent to Google Gemini for object detection. They are <strong>not stored</strong> on MemoryMap&apos;s servers.
            </span>
          </li>
          <li className="flex gap-2 items-start">
            <span className="text-indigo-500 shrink-0 mt-0.5">•</span>
            <span>
              When patients ask questions, MemoryMap monitors for signs of confusion or repeated questions. If detected, <strong>caregivers are notified</strong> so they can check in.
            </span>
          </li>
          <li className="flex gap-2 items-start">
            <span className="text-indigo-500 shrink-0 mt-0.5">•</span>
            <span>
              Your room maps, tags, and account data are stored privately in a secure database accessible only to your account.
            </span>
          </li>
          <li className="flex gap-2 items-start">
            <span className="text-indigo-500 shrink-0 mt-0.5">•</span>
            <span>
              You can delete all your data at any time from <strong>Settings</strong>.
            </span>
          </li>
        </ul>

        <button
          onClick={handleAccept}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl py-3 text-base font-medium transition"
        >
          I understand — let&apos;s go
        </button>
      </div>
    </div>
  )
}
