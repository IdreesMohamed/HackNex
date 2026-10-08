import { createClient as createBrowserClient } from './supabase/client'

let browserClient: ReturnType<typeof createBrowserClient> | null = null

export function getSupabaseClient() {
  if (!browserClient) browserClient = createBrowserClient()
  return browserClient
}
