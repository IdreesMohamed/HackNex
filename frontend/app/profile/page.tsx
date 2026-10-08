'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { getSupabaseClient } from '../../lib/supabase'

export default function ProfilePage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => { const supabase = getSupabaseClient(); if (!supabase) { setLoading(false); return } supabase.auth.getUser().then(({ data }) => { setEmail(data.user?.email ?? '') ; setLoading(false) }).catch(() => setLoading(false)) }, [])
  async function signOut() { const supabase = getSupabaseClient(); if (supabase) await supabase.auth.signOut(); window.location.href = '/auth/login' }
  return <main className="page-shell narrow-page"><section className="page-hero compact-hero"><div><p className="eyebrow">ACCOUNT</p><h1>Your workspace.</h1><p className="page-lede">Manage the preferences that make every conversation feel familiar.</p></div><Link className="secondary-button" href="/app">Back to room</Link></section><section className="settings-grid"><article className="surface-card"><p className="eyebrow">PROFILE</p><h2>{loading ? 'Loading account…' : 'Translation operator'}</h2><p className="muted">{email || 'No active session'}</p><div className="profile-avatar">{email ? email.slice(0, 2).toUpperCase() : 'HN'}</div><button className="ghost-button" onClick={signOut} disabled={!email}>Sign out</button></article><article className="surface-card"><p className="eyebrow">PREFERENCES</p><label className="setting-row"><span>Auto-detect source language</span><input type="checkbox" defaultChecked /></label><label className="setting-row"><span>Show confidence scores</span><input type="checkbox" defaultChecked /></label><label className="setting-row"><span>Reduce motion</span><input type="checkbox" /></label></article></section></main>
} 
