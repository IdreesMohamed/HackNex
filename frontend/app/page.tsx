'use client'

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { DemoTranslationConnector, type CaptionSegment, type ConnectionState } from '../lib/connectors'

const languages = [
  { value: 'Tamil', native: 'தமிழ்', code: 'TA' },
  { value: 'Hindi', native: 'हिन्दी', code: 'HI' },
  { value: 'English', native: 'English', code: 'EN' },
  { value: 'Malayalam', native: 'മലയാളം', code: 'ML' },
  { value: 'Spanish', native: 'Español', code: 'ES' },
  { value: 'French', native: 'Français', code: 'FR' },
  { value: 'German', native: 'Deutsch', code: 'DE' },
  { value: 'Japanese', native: '日本語', code: 'JA' },
]

const initialSegments: CaptionSegment[] = [
  { id: '1', source: 'இன்று நாம் மொழிகளுக்கு இடையே உள்ள தடைகளை உடைக்கிறோம்.', translation: 'Today, we are breaking the barriers between languages.', timestamp: '00:02', confidence: 0.99 },
  { id: '2', source: 'ஒவ்வொருவரும் தங்கள் குரலில் பங்கேற்கலாம்.', translation: 'Everyone can participate in their own voice.', timestamp: '00:08', confidence: 0.97 },
]

const statusCopy: Record<ConnectionState, string> = { idle: 'Paused', connecting: 'Connecting', listening: 'Listening live', degraded: 'Degraded', ended: 'Session ended', error: 'Connection error' }

export default function Home() {
  const [sourceLanguage, setSourceLanguage] = useState('Tamil')
  const [targetLanguage, setTargetLanguage] = useState('English')
  const [state, setState] = useState<ConnectionState>('listening')
  const [segments, setSegments] = useState(initialSegments)
  const [activeView, setActiveView] = useState<'translate' | 'notes' | 'history'>('translate')
  const [showSettings, setShowSettings] = useState(false)
  const [showParticipants, setShowParticipants] = useState(false)
  const [search, setSearch] = useState('')
  const [autoDetect, setAutoDetect] = useState(false)
  const [voicePlayback, setVoicePlayback] = useState(true)
  const [speakerLabels, setSpeakerLabels] = useState(true)
  const [saveTranscript, setSaveTranscript] = useState(true)
  const [actionItems, setActionItems] = useState(['Share the translated transcript with the team', 'Schedule the next multilingual session', 'Review terminology preferences'])
  const [newActionItem, setNewActionItem] = useState('')
  const [copied, setCopied] = useState(false)
  const [micError, setMicError] = useState('')
  const [audioLevel, setAudioLevel] = useState(0)
  const [isRecording, setIsRecording] = useState(false)
  const connector = useRef(new DemoTranslationConnector())
  const mediaRecorder = useRef<MediaRecorder | null>(null)
  const mediaStream = useRef<MediaStream | null>(null)
  const audioContext = useRef<AudioContext | null>(null)
  const meterFrame = useRef<number | null>(null)
  const isLive = state === 'listening' || state === 'connecting'
  const latest = useMemo(() => segments[segments.length - 1], [segments])
  const filteredSegments = segments.filter((segment) => `${segment.source} ${segment.translation}`.toLowerCase().includes(search.toLowerCase()))

  useEffect(() => {
    const handleSpace = (event: KeyboardEvent) => {
      if (event.code === 'Space' && event.target instanceof HTMLElement && !['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(event.target.tagName)) {
        event.preventDefault()
        void toggleSession()
      }
    }
    window.addEventListener('keydown', handleSpace)
    const unsubscribeState = connector.current.onStateChange(setState)
    const unsubscribeCaption = connector.current.onCaption((segment) => setSegments((current) => [...current, segment]))
    return () => {
      window.removeEventListener('keydown', handleSpace)
      unsubscribeState()
      unsubscribeCaption()
    }
  }, [])

  useEffect(() => () => {
    if (meterFrame.current) cancelAnimationFrame(meterFrame.current)
    mediaStream.current?.getTracks().forEach((track) => track.stop())
    audioContext.current?.close()
  }, [])

  async function startMicrophone() {
    setMicError('')
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicError('Microphone capture is not supported in this browser.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      mediaStream.current = stream
      const recorder = new MediaRecorder(stream)
      mediaRecorder.current = recorder
      recorder.ondataavailable = async (event) => {
        if (event.data.size > 0) connector.current.sendAudio?.(await event.data.arrayBuffer())
      }
      recorder.start(250)
      setIsRecording(true)
      const context = new AudioContext()
      audioContext.current = context
      const analyser = context.createAnalyser()
      analyser.fftSize = 256
      context.createMediaStreamSource(stream).connect(analyser)
      const data = new Uint8Array(analyser.frequencyBinCount)
      const measure = () => {
        analyser.getByteFrequencyData(data)
        const average = data.reduce((sum, value) => sum + value, 0) / data.length
        setAudioLevel(Math.min(100, Math.round(average * 1.8)))
        meterFrame.current = requestAnimationFrame(measure)
      }
      measure()
    } catch {
      setMicError('Microphone access was blocked. Allow microphone permission and try again.')
      setIsRecording(false)
    }
  }

  function stopMicrophone() {
    mediaRecorder.current?.stop()
    mediaStream.current?.getTracks().forEach((track) => track.stop())
    mediaRecorder.current = null
    mediaStream.current = null
    if (meterFrame.current) cancelAnimationFrame(meterFrame.current)
    audioContext.current?.close()
    audioContext.current = null
    setAudioLevel(0)
    setIsRecording(false)
  }

  async function handleAudioFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setMicError('')
    const buffer = await file.arrayBuffer()
    connector.current.sendAudio?.(buffer)
    setIsRecording(true)
    window.setTimeout(() => setIsRecording(false), Math.min(30000, Math.max(1200, file.size / 80)))
  }

  async function toggleSession() {
    if (!isRecording) await startMicrophone()
    if (isLive) await connector.current.pause()
    else if (state === 'ended') { setSegments([]); await connector.current.connect({ sourceLanguage, targetLanguage }) }
    else await connector.current.resume()
  }
  async function finishSession() { stopMicrophone(); await connector.current.end() }
  function swapLanguages() { setSourceLanguage(targetLanguage); setTargetLanguage(sourceLanguage) }
  function exportTranscript() {
    const text = segments.map((segment) => `[${segment.timestamp}] ${segment.source}\n${segment.translation}`).join('\n\n')
    const blob = new Blob([`HackNex Live transcript\n${sourceLanguage} → ${targetLanguage}\n\n${text}`], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `hacknex-${new Date().toISOString().slice(0, 10)}.txt`
    link.click()
    URL.revokeObjectURL(url)
  }

  function addActionItem() {
    const item = newActionItem.trim()
    if (!item) return
    setActionItems((current) => [...current, item])
    setNewActionItem('')
  }

  async function copyRoomCode() {
    await navigator.clipboard.writeText('HN-2048')
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup"><span className="brand-mark">H</span><span>HackNex <b>Live</b></span></div>
        <nav className="main-nav" aria-label="Workspace navigation">
          {(['translate', 'notes', 'history'] as const).map((view) => <button key={view} className={activeView === view ? 'nav-active' : ''} onClick={() => setActiveView(view)}>{view === 'translate' ? 'Live room' : view === 'notes' ? 'AI notes' : 'Session history'}</button>)}
        </nav>
        <div className="topbar-actions"><button className="session-label" onClick={copyRoomCode} aria-label="Copy room code">ROOM <strong>HN-2048</strong>{copied ? ' · Copied' : ''}</button><button className="top-action" onClick={() => setShowParticipants((current) => !current)}>● 4 live</button><button className="icon-button" aria-label="Open settings" onClick={() => setShowSettings((current) => !current)}>⚙</button><div className="avatar" aria-label="Account">AM</div></div>
      </header>

      <section className="workspace">
        <div className="workspace-heading"><div><p className="eyebrow">LIVE TRANSLATION ROOM / 01</p><h1>Your words, understood.</h1><p className="subhead">A shared voice layer for meetings, classrooms, and everyday conversations.</p></div><div className="heading-actions"><div className="status-pill"><span className={`status-dot ${isLive ? 'pulse' : ''}`} />{statusCopy[state]}</div><button className="ghost-button" onClick={exportTranscript}>Export transcript ↗</button></div></div>

        <div className="feature-strip"><div><span className="strip-icon">◉</span><span><b>Live captions</b><small>Instant source + translated speech</small></span></div><div><span className="strip-icon coral-icon">✦</span><span><b>AI meeting notes</b><small>Highlights and action items, automatically</small></span></div><div><span className="strip-icon">⌁</span><span><b>12ms audio handoff</b><small>Natural voice playback on every device</small></span></div><span className="powered">Built for 70+ languages</span></div>

        {activeView === 'translate' && <>
          <div className="language-bar"><label><span>Speaking</span><select value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value)}>{languages.map((language) => <option key={language.value} value={language.value}>{language.value} · {language.native}</option>)}</select></label><button className="swap-button" onClick={swapLanguages} aria-label="Swap languages">⇄</button><label><span>Translate to</span><select value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}>{languages.map((language) => <option key={language.value} value={language.value}>{language.value} · {language.native}</option>)}</select></label><div className="latency"><span>LATENCY</span><strong>0.8s</strong></div><label className="toggle-label"><span>Auto-detect</span><button className={`toggle ${autoDetect ? 'on' : ''}`} onClick={() => setAutoDetect(!autoDetect)} aria-label="Toggle auto-detect"><i /></button></label></div>
          <div className="caption-grid"><section className="caption-panel source-panel"><div className="panel-label"><span><i className="language-dot teal" />{sourceLanguage}</span><span className="live-label">LIVE</span></div><div className="captions">{filteredSegments.map((segment) => <p className="caption-line" key={segment.id}>{segment.source}<small>{segment.timestamp}</small></p>)}{isLive && <p className="caption-line partial">{latest?.source ?? 'Start speaking to see your words here…'}<span className="cursor" /></p>}</div><div className="panel-footer"><span>Source transcript</span><span>{autoDetect ? 'Auto-detect on' : 'Auto-detect off'}</span></div></section><section className="caption-panel translation-panel"><div className="panel-label"><span><i className="language-dot coral" />{targetLanguage}</span><span className="stable-label">STABLE</span></div><div className="captions">{filteredSegments.map((segment) => <p className="caption-line" key={segment.id}>{segment.translation}<small>{Math.round((segment.confidence ?? .98) * 100)}% match</small></p>)}{isLive && <p className="caption-line partial">{latest?.translation ?? 'Translation will appear here…'}<span className="cursor coral-cursor" /></p>}</div><div className="panel-footer"><span>Translated output</span><span>Voice playback ready</span></div></section></div>
          <div className="control-row"><div className="control-meta"><span className="mic-wave"><i /><i /><i /><i /><i /></span><span>{isRecording ? 'Microphone active' : isLive ? 'Microphone ready' : 'Microphone paused'}</span><span className="audio-badge">Audio output on</span><span className="level-meter" aria-label={`Audio level ${audioLevel}%`}><i style={{ width: `${audioLevel}%` }} /></span></div><div className="controls"><label className="upload-button">Upload WAV<input type="file" accept="audio/wav,audio/wave,audio/*" onChange={handleAudioFile} /></label><button className={`mic-button ${isLive ? 'active' : ''}`} onClick={toggleSession} aria-label={isLive ? 'Pause microphone' : 'Resume microphone'}><span>{isLive ? 'Ⅱ' : '▶'}</span></button><button className="end-button" onClick={finishSession}>End session</button></div><span className="keyboard-hint">SPACE <em>to pause</em></span></div>{micError && <p className="mic-error" role="alert">{micError}</p>}
        </>}

        {activeView === 'notes' && <section className="notes-view"><div className="notes-header"><div><p className="eyebrow">AI SESSION SUMMARY</p><h2>Conversation intelligence</h2><p>Generated live from your translated room. Edit, share, or export when ready.</p></div><button className="primary-button" onClick={exportTranscript}>Export notes ↗</button></div><div className="notes-grid"><article className="note-card accent-card"><span className="note-tag">KEY TAKEAWAYS</span><h3>Everyone can participate in their own voice.</h3><p>The conversation focused on making communication more inclusive across language boundaries.</p><div className="note-footer">Generated just now <span>98% confidence</span></div></article><article className="note-card"><span className="note-tag">ACTION ITEMS</span><ul>{actionItems.map((item) => <li key={item}>{item}</li>)}</ul><div className="add-action"><input value={newActionItem} onChange={(event) => setNewActionItem(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.nativeEvent.isComposing && event.keyCode !== 229) addActionItem() }} placeholder="New action item" aria-label="New action item" /><button className="add-button" onClick={addActionItem}>+ Add action item</button></div></article><article className="note-card"><span className="note-tag">TOPICS</span><div className="topic-list"><span>Accessibility</span><span>Global teams</span><span>Product strategy</span><span>Inclusive design</span></div></article></div></section>}

        {activeView === 'history' && <section className="history-view"><div className="notes-header"><div><p className="eyebrow">YOUR WORKSPACE</p><h2>Session history</h2><p>Find, revisit, and share every conversation.</p></div><div className="search-box">⌕ <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search sessions" /></div></div><div className="history-list"><div className="history-item"><span className="history-date">TODAY<br /><b>10:42 AM</b></span><span className="history-main"><b>Global team kickoff</b><small>Tamil → English · 24 min · 4 participants</small></span><span className="history-status">Translated</span><button className="more-button">•••</button></div><div className="history-item"><span className="history-date">YESTERDAY<br /><b>03:18 PM</b></span><span className="history-main"><b>Design review — Chennai</b><small>Hindi → English · 48 min · 8 participants</small></span><span className="history-status">Translated</span><button className="more-button">•••</button></div></div></section>}

        {showSettings && <aside className="settings-panel"><div className="panel-title"><div><p className="eyebrow">WORKSPACE SETTINGS</p><h2>Room controls</h2></div><button className="close-button" onClick={() => setShowSettings(false)}>×</button></div><label className="setting-row"><span>Voice playback</span><input type="checkbox" checked={voicePlayback} onChange={(event) => setVoicePlayback(event.target.checked)} /></label><label className="setting-row"><span>Speaker labels</span><input type="checkbox" checked={speakerLabels} onChange={(event) => setSpeakerLabels(event.target.checked)} /></label><label className="setting-row"><span>Save transcript automatically</span><input type="checkbox" checked={saveTranscript} onChange={(event) => setSaveTranscript(event.target.checked)} /></label><div className="setting-row"><span>Translation engine</span><b>Sarvam Realtime <small>Connected</small></b></div><div className="provider-row"><span className="provider-icon">S</span><span><strong>Sarvam realtime</strong><small>Primary provider · 0.8s average</small></span><span className="connected">Connected</span></div></aside>}
        {showParticipants && <aside className="participants-panel"><div className="panel-title"><div><p className="eyebrow">LIVE ROOM</p><h2>Participants <span>4</span></h2></div><button className="close-button" onClick={() => setShowParticipants(false)}>×</button></div>{['Ananya Menon', 'Ravi Kumar', 'Sofia Chen', 'You'].map((name, index) => <div className="participant" key={name}><span className={`participant-avatar avatar-${index}`}>{name.split(' ').map((word) => word[0]).join('')}</span><span><b>{name}</b><small>{index === 3 ? 'Host · speaking' : index === 0 ? 'Speaking Tamil' : 'Listening in English'}</small></span><i className={index === 3 ? 'speaking' : ''} /></div>)}<button className="invite-button">+ Invite participants</button></aside>}
        <footer className="bottom-bar"><span><b>HackNex 2026</b> · Live translation for Indic languages</span><span>Private by design · Built for every voice <span className="footer-mark">+</span></span></footer>
      </section>
    </main>
  )
}
