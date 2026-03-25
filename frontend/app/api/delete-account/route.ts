import { NextRequest, NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'

export async function POST(request: NextRequest) {
  const authHeader = request.headers.get('Authorization')
  const token = authHeader?.replace('Bearer ', '')

  if (!token) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  // Verify the user via the anon client first
  const anonClient = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => [], setAll: () => {} } }
  )

  const { data: { user }, error: userError } = await anonClient.auth.getUser(token)

  if (userError || !user) {
    return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
  }

  // Service role client — bypasses RLS for cleanup
  const serviceClient = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    {
      cookies: { getAll: () => [], setAll: () => {} },
      auth: { autoRefreshToken: false, persistSession: false },
    }
  )

  try {
    // Find all storage paths for this user's photos
    const { data: homes } = await serviceClient
      .from('homes')
      .select('id')
      .eq('owner_id', user.id)

    if (homes?.length) {
      const homeIds = homes.map((h: { id: string }) => h.id)

      const { data: rooms } = await serviceClient
        .from('rooms')
        .select('id')
        .in('home_id', homeIds)

      if (rooms?.length) {
        const roomIds = rooms.map((r: { id: string }) => r.id)

        const { data: photos } = await serviceClient
          .from('photos')
          .select('storage_path')
          .in('room_id', roomIds)

        // Delete all storage objects
        if (photos?.length) {
          const paths = photos.map((p: { storage_path: string }) => p.storage_path)
          await serviceClient.storage.from('photos').remove(paths)
        }
      }

      // Delete homes (cascades to rooms, photos, tags via FK)
      await serviceClient.from('homes').delete().in('id', homeIds)
    }

    // Delete the auth user
    const { error: deleteError } = await serviceClient.auth.admin.deleteUser(user.id)
    if (deleteError) throw deleteError

    return NextResponse.json({ success: true })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Deletion failed'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
