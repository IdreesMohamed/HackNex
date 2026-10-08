import { createClient } from '../../../lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get('code')
  const next = request.nextUrl.searchParams.get('next') ?? '/app'
  const safeNext = next.startsWith('/') && !next.startsWith('//') ? next : '/app'
  if (code) {
    const supabase = await createClient()
    const { error } = await supabase.auth.exchangeCodeForSession(code)
    if (!error) return NextResponse.redirect(new URL(safeNext, request.url))
  }
  return NextResponse.redirect(new URL('/auth/login?error=callback', request.url))
}
