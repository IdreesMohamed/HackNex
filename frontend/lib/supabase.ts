import { createClient } from '@supabase/supabase-js'

let browserClient: ReturnType<typeof createClient> | null = null

export function getSupabaseClient() {
  if (!browserClient) {
    browserClient = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    )
  }

  return browserClient
}
