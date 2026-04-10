'use client'

interface Props {
  onAccept: () => void
}

/**
 * Shown once to patients on first visit to the query page.
 * Explains that queries are monitored for safety and caregivers may be notified.
 */
export function BackgroundConsentModal({ onAccept }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 px-4 pb-4 sm:pb-0">
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6">
        <div className="text-3xl mb-3 text-center">💙</div>
        <h2 className="text-lg font-semibold text-gray-900 text-center mb-3">
          We&apos;re here to help
        </h2>

        <ul className="space-y-3 text-sm text-gray-600 mb-5">
          <li className="flex gap-2 items-start">
            <span className="text-indigo-500 shrink-0 mt-0.5">•</span>
            <span>When you ask questions, MemoryMap remembers to give you faster answers next time.</span>
          </li>
          <li className="flex gap-2 items-start">
            <span className="text-indigo-500 shrink-0 mt-0.5">•</span>
            <span>Your caregiver may be notified if MemoryMap notices you seem confused or need extra help — so they can check in on you.</span>
          </li>
          <li className="flex gap-2 items-start">
            <span className="text-indigo-500 shrink-0 mt-0.5">•</span>
            <span>You are always in control. Your caregiver wants to keep you safe.</span>
          </li>
        </ul>

        <button
          onClick={onAccept}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl py-3 text-base font-medium transition"
        >
          Got it, let&apos;s go
        </button>
      </div>
    </div>
  )
}
