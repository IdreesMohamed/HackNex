'use client'

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import Link from 'next/link'
import { getSupabaseClient } from '../../lib/supabase'
import { audioFileIsWav, createRoomId, createTranslationAdapter, downloadFile, formatEventTime, formatMetric, seconds, supportedLanguages, type TranslationEvent } from '../../lib/translation/client'

type Segment = { source: string; translation: string; partial: boolean; time: string; confidence?: number }
type SessionState = 'idle' | 'requesting-permission' | 'connecting' | 'listening' | 'paused' | 'reconnecting' | 'error' | 'stopped'

const native: Record<string, string> = { Tamil: 'தமிழ்', Hindi: 'हिन्दी', English: 'English', Kannada: 'ಕನ್ನಡ', Telugu: 'తెలుగు', Malayalam: 'മലയാളം' }

export default function LiveRoom() {
  const [ready, setReady] = useState(false)
  const [email, setEmail] = useState('')
  const [state, setState] = useState<SessionState>('idle')
  const [source, setSource] = useState('Tamil')
  const [target, setTarget] = useState('English')
  const [auto, setAuto] = useState(false)
  const [detected, setDetected] = useState('')
  const [segments, setSegments] = useState<Segment[]>([])
  const [error, setError] = useState('')
  const [level, setLevel] = useState(0)
  const [first, setFirst] = useState<number>()
  const [final, setFinal] = useState<number>()
  const [terms, setTerms] = useState<string[]>([])
  const [term, setTerm] = useState('')
  const [consent, setConsent] = useState(false)
  const [room, setRoom] = useState('')
  const [sessionId, setSessionId] = useState<string>()
  const [stabilityOpen, setStabilityOpen] = useState(false)
  const [startedAt, setStartedAt] = useState<number>()
  const [elapsed, setElapsed] = useState(0)
  const adapter = useRef(createTranslationAdapter())
  const stream = useRef<MediaStream | null>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const live = ['requesting-permission', 'connecting', 'listening', 'paused', 'reconnecting'].includes(state)
  const latest = segments.at(-1)

  useEffect(() => {
    try {
      const supabase = getSupabaseClient()
      if (!supabase) { setReady(true); return }
      supabase.auth.getUser().then(({ data }) => { setEmail(data.user?.email ?? ''); setReady(true) }).catch(() => { setEmail(''); setReady(true) })
    } catch {
      setEmail('')
      setReady(true)
    }
    return () => { stream.current?.getTracks().forEach((track) => track.stop()) }
  }, [])
  useEffect(() => { if (!startedAt || !live) return; const timer = window.setInterval(() => setElapsed(Date.now() - startedAt), 1000); return () => window.clearInterval(timer) }, [startedAt, live])

  function handleEvent(event: TranslationEvent) {
    if (event.type === 'language_detected') setDetected(event.language)
    if (event.type === 'metrics') { setFirst(event.timeToFirstWordMs); setFinal(event.endOfSpeechToFinalMs) }
      if (event.type === 'error') { setError(event.message); setState('error') }
    const supabase = getSupabaseClient()
    if (supabase && sessionId && event.type !== 'metrics') void supabase.from('translation_sessions').update({ transcript: segments }).eq('id', sessionId)
    if (['partial_source', 'partial_translation', 'committed_translation', 'final_translation'].includes(event.type)) {
      const text = 'text' in event ? event.text : ''
      setSegments((current) => {
        const previous = current.at(-1)
        const next: Segment = { source: previous?.source ?? '', translation: previous?.translation ?? '', partial: event.type.startsWith('partial'), time: formatEventTime(event.timestampMs), confidence: 'confidence' in event ? event.confidence : undefined }
        if (event.type.includes('source')) next.source = text
        else next.translation = text
        return previous?.partial ? [...current.slice(0, -1), next] : [...current, next]
      })
    }
  }
  async function connect() {
    setError(''); if (!consent) { setError('Microphone access is required for live translation. Accept recording consent before starting.'); return }
    if (!navigator.mediaDevices?.getUserMedia) { setError('This browser does not support microphone capture.'); setState('error'); return }
    setState('requesting-permission')
    if (!getSupabaseClient()) { setError('Supabase is not configured in this preview.'); setState('error'); return }
    try {
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true }); stream.current = audioStream
      const mediaRecorder = new MediaRecorder(audioStream); recorder.current = mediaRecorder
      mediaRecorder.ondataavailable = async (event) => { if (event.data.size) adapter.current.sendAudio(await event.data.arrayBuffer()) }
      mediaRecorder.start(250); setState('connecting'); adapter.current.onEvent(handleEvent)
      await adapter.current.connect({ sourceLanguage: source, targetLanguage: target, glossary: terms, autoDetect: auto })
      const supabase = getSupabaseClient()
      const { data: userData } = await supabase.auth.getUser()
      const sessionCode = createRoomId()
      if (!userData.user) throw new Error('Please sign in again before starting a session.')
      const { data: savedSession, error: saveError } = await supabase.from('translation_sessions').insert({ user_id: userData.user.id, session_code: sessionCode, source_language: source, target_language: target, status: 'live' }).select('id').single()
      if (saveError) throw saveError
      setSessionId(savedSession.id); setRoom(sessionCode); setStartedAt(Date.now()); setState('listening'); setLevel(42)
    } catch (cause) { setError(cause instanceof DOMException && cause.name === 'NotAllowedError' ? 'Microphone access is required for live translation.' : 'Unable to start microphone capture. Check that a microphone is connected.'); setState('error') }
  }
  async function stop() { recorder.current?.stop(); stream.current?.getTracks().forEach((track) => track.stop()); await adapter.current.end(); const supabase = getSupabaseClient(); if (supabase && sessionId) await supabase.from('translation_sessions').update({ status: 'ended', transcript: segments, ended_at: new Date().toISOString() }).eq('id', sessionId); setState('stopped'); setLevel(0) }
  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; if (!file) return
    if (!audioFileIsWav(file)) { setError('Please choose a WAV file.'); return }
    if (!consent) { setError('Accept recording consent before uploading.'); return }
    setError(''); setState('connecting'); adapter.current.onEvent(handleEvent); await adapter.current.connect({ sourceLanguage: source, targetLanguage: target, glossary: terms, autoDetect: auto }); adapter.current.sendAudio(await file.arrayBuffer()); setRoom(createRoomId()); setStartedAt(Date.now()); setState('listening')
  }
  function addTerm() { const value = term.trim(); if (value && !terms.includes(value)) { setTerms((current) => [...current, value]); setTerm('') } }
  const status = { idle: 'Ready', stopped: 'Session complete', 'requesting-permission': 'Requesting microphone', connecting: 'Connecting', listening: 'Live', paused: 'Paused', reconnecting: 'Reconnecting', error: 'Connection interrupted' }[state]
  const sourceLabel = native[source]
  const targetLabel = native[target]
  const history = useMemo(() => segments.slice(-5).reverse(), [segments])

  if (!ready) return <main className="app-shell"><section className="auth-gate"><span className="brand-mark">H</span><p className="eyebrow">LIVE TRANSLATION</p><h1>Checking your session.</h1></section></main>
  if (!email) return <main className="app-shell"><section className="auth-gate"><span className="brand-mark">H</span><p className="eyebrow">PROTECTED LIVE ROOM</p><h1>Sign in to translate.</h1><p className="subhead">Your transcripts and usage belong to your account.</p><Link className="primary-button" href="/auth/login">Sign in</Link></section></main>

  return <main className="app-shell">
    <section className="room-shell">
      <div className="room-heading"><div><p className="eyebrow">HNX26EPS03 / LIVE TRANSLATION</p><h1>Translate conversations.<br /><span>In real time.</span></h1><p className="subhead">Stable captions for multilingual rooms, with honest latency.</p></div><div className="room-actions"><label className="upload-button">Upload WAV<input type="file" accept="audio/wav,.wav" onChange={upload} disabled={live} /></label><button className={live ? 'danger-button' : 'primary-button'} onClick={live ? stop : connect} disabled={state === 'requesting-permission' || state === 'connecting'}>{state === 'requesting-permission' ? 'Requesting…' : state === 'connecting' ? 'Connecting…' : live ? 'End session' : 'Start microphone'}</button></div></div>
      {error && <div className="alert error-alert" role="alert"><span>!</span><div><strong>{error}</strong><p>Check your device permissions or reconnect to continue.</p></div><button onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
      <div className="room-grid">
        <section className="primary-column">
          <div className="language-switcher panel"><div className="language-field"><span className="panel-label">Speaking</span><button className="language-select" disabled={live} onClick={() => {}}><span>{sourceLabel}</span><small>{source}</small><b>⌄</b></button></div><button className="swap-button" aria-label="Swap languages" onClick={() => { setSource(target); setTarget(source) }} disabled={live}>⇄</button><div className="language-field"><span className="panel-label">Translate to</span><button className="language-select" disabled={live}><span>{targetLabel}</span><small>{target}</small><b>⌄</b></button></div><label className="auto-detect"><input type="checkbox" checked={auto} onChange={(event) => setAuto(event.target.checked)} disabled={live} /><span><b>Auto-detect</b><small>{detected ? `Detected ${detected}` : 'Listen for source language'}</small></span></label></div>
          <section className="caption-workspace panel"><div className="caption-topline"><span className="panel-label">LIVE CAPTIONS</span><span className={`live-badge ${live ? 'active' : ''}`}><i className="dot" />{live ? 'LIVE' : 'IDLE'}</span></div><div className="source-caption"><span className="caption-language">{sourceLabel} <small>{source}</small></span><p>{latest?.source || 'Start speaking to see your words here.'}</p></div><div className="caption-divider" /><div className="translation-caption"><span className="caption-language">{targetLabel} <small>{target}</small></span><p className={latest?.partial ? 'provisional' : ''}>{latest?.translation || 'Your translated speech appears here.'}{live && <span className="caret" />}</p></div>{!live && <span className="demo-note">Demo recording · No live audio is active</span>}</section>
          <div className="audio-strip panel"><div className="audio-state"><button className={`mic-button ${live ? 'active' : ''}`} onClick={live ? stop : connect} aria-label={live ? 'Stop microphone' : 'Start microphone'}><span>◉</span></button><div><strong>{live ? 'Listening…' : 'Start speaking'}</strong><small>{live ? 'Microphone active' : 'Press to begin a live session'}</small></div></div><div className="waveform" aria-label={`Audio level ${level}%`}>{Array.from({ length: 28 }, (_, index) => <i key={index} style={{ height: `${live ? Math.max(10, ((index * 17 + level) % 52)) : 10}%` }} />)}</div><div className="audio-time"><strong>{startedAt ? `${String(Math.floor(elapsed / 60000)).padStart(2, '0')}:${String(Math.floor(elapsed / 1000) % 60).padStart(2, '0')}` : '00:00'}</strong><small>SESSION</small></div></div>
          <div className="control-row"><button className="secondary-button" onClick={() => setState(state === 'paused' ? 'listening' : 'paused')} disabled={!live}>{state === 'paused' ? 'Resume' : 'Pause'}</button><button className="secondary-button" onClick={() => { setSource(target); setTarget(source) }} disabled={live}>⇄ Swap</button><span className="consent-control"><input type="checkbox" id="consent" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><label htmlFor="consent">I consent to microphone recording for this session.</label></span></div>
        </section>
        <aside className="side-column"><section className="panel metrics-panel"><div className="panel-heading"><div><span className="panel-label">PERFORMANCE</span><h2>Measured in real time</h2></div><span className="verified-mark">✓</span></div><div className="metric-grid"><Metric label="Time to first word" value={formatMetric(first)} /><Metric label="End of speech → final" value={formatMetric(final)} /><Metric label="Confidence" value={latest?.confidence == null ? 'Not measured' : `${Math.round(latest.confidence * 100)}%`} /></div></section><section className="panel stability-panel"><button className="expand-button" onClick={() => setStabilityOpen(!stabilityOpen)}><span><span className="panel-label">AI STABILITY</span><strong><i className="stable-dot" />Stable prefix</strong></span><b>{stabilityOpen ? '−' : '+'}</b></button>{stabilityOpen && <div className="stability-detail"><span className="panel-label">REALTIME HYPOTHESES</span><p>“Where are you going…”</p><p>“Where are you going…”</p><div className="stable-prefix">↓ Stable prefix<br /><strong>“Where are you going…”</strong></div><span className="committed-label">COMMITTED</span></div>}</section><section className="panel glossary-panel"><div className="panel-heading"><div><span className="panel-label">GLOSSARY</span><h2>Preferred terms</h2></div><span className="chip">{terms.length}</span></div><div className="term-input"><input value={term} onChange={(event) => setTerm(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') addTerm() }} placeholder="Add a term" /><button onClick={addTerm}>+</button></div><div className="term-list">{terms.map((value) => <span key={value} className="term-chip">{value}<button onClick={() => setTerms(terms.filter((item) => item !== value))} aria-label={`Remove ${value}`}>×</button></span>)}</div></section></aside>
      </div>
      <section className="history-section"><div className="section-heading"><div><span className="panel-label">SESSION HISTORY</span><h2>Recent captions</h2></div><span className="mono">{segments.length} SEGMENTS</span></div>{history.length ? <div className="history-list">{history.map((item, index) => <article className={`history-item ${index === 0 ? 'latest' : ''}`} key={`${item.time}-${index}`}><span className="mono">{item.time}</span><div><small>{sourceLabel}</small><p>{item.source || '—'}</p><small>{targetLabel}</small><p className={item.partial ? 'provisional' : ''}>{item.translation || '—'}</p></div></article>)}</div> : <div className="empty-history"><span>◎</span><p>Your committed captions will appear here.</p><small>Start a session to begin building a transcript.</small></div>}</section>
      <section className="pipeline-section"><div><span className="panel-label">HOW IT WORKS</span><h2>From voice to understanding.</h2></div><div className="pipeline">{[['◉', 'Audio', 'Capture clear speech'], ['⌁', 'Realtime ASR', 'Convert speech to text'], ['✦', 'Stability engine', 'Commit only stable words'], ['→', 'Translation', 'Preserve meaning'], ['≡', 'Live captions', 'Read it instantly']].map(([icon, title, description], index) => <div className="pipeline-step" key={title}><span>{icon}</span><div><strong>{title}</strong><small>{description}</small></div>{index < 4 && <b>→</b>}</div>)}</div></section>
    </section>
  </main>
}
function Metric({ label, value }: { label: string; value: string }) { return <div className="metric-item"><span className="metric-label">{label}</span><b>{value}</b></div> }
function CaptionPanel() { return null }
void seconds; void downloadFile
