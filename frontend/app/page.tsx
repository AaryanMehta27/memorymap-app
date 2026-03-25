import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import Link from 'next/link'

export default async function Home() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (user) redirect('/dashboard')

  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gray-50 px-4 text-center">
      <h1 className="text-4xl font-bold text-gray-900 mb-3">MemoryMap</h1>
      <p className="text-lg text-gray-500 mb-8 max-w-md">
        Helping patients with memory loss find things in their home — with the help of AI and caregivers.
      </p>
      <div className="flex gap-3">
        <Link
          href="/auth/register"
          className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg px-5 py-2.5 text-sm transition"
        >
          Get started
        </Link>
        <Link
          href="/auth/login"
          className="bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 font-medium rounded-lg px-5 py-2.5 text-sm transition"
        >
          Sign in
        </Link>
      </div>
    </main>
  )
}
