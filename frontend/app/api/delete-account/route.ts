import { NextResponse } from 'next/server'
import { createClient as createServerClient } from '@supabase/supabase-js'

export async function POST(request: Request) {
  const authHeader = request.headers.get('Authorization')
  if (!authHeader) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  const token = authHeader.replace('Bearer ', '')
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  )
  const { data: { user }, error: userError } = await supabase.auth.getUser(token)
  if (userError || !user) return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
  await supabase.from('user_roles').delete().eq('user_id', user.id)
  const { data: homeRow } = await supabase.from('homes').select('id').eq('owner_id', user.id).single()
  if (homeRow) {
    await supabase.from('rooms').delete().eq('home_id', homeRow.id)
    await supabase.from('homes').delete().eq('id', homeRow.id)
  }
  const { error: deleteError } = await supabase.auth.admin.deleteUser(user.id)
  if (deleteError) return NextResponse.json({ error: deleteError.message }, { status: 500 })
  return NextResponse.json({ success: true })
}
