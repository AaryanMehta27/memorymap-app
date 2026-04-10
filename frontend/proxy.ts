import { NextResponse, type NextRequest } from 'next/server'

// Supabase auth check disabled until DNS is resolved — pages handle auth themselves
export function proxy(request: NextRequest) {
  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
