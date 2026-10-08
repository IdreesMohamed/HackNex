'use client'

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { applyMetrics, connectionStatus, createDemoAdapter, createSessionId, demoLabel, demoSample, displayConfidence, formatTimestamp, isLiveState, metricText, reduceAdapterEvent, speak, statusForAudio, statusForVoice, stopVoice, supportsSpeechSynthesis, type CaptionSegment, type ConnectionState, type MeasuredMetrics } from '../lib/connectors'
import { getSupabaseClient } from '../lib/supabase'

const languages = ['Tamil', 'Hindi', 'English', 'Malayalam']

export default function Home() {
  const [sourceLanguage, setSourceLanguage] = useState('Tamil')
  const [targetLanguage, setTargetLanguage] = useState('English')
  const [state, setState] = useState<ConnectionState>('ended')
  const [segments, setSegments] = useState<CaptionSegment[]>([])
  const [metrics, setMetrics] = useState<MeasuredMetrics>({})
  const [detectedLanguage, setDetectedLanguage] = useState('')
  const [autoDetect, setAutoDetect] = useState(false)
  const [voicePlayback, setVoicePlayback] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [roomId, setRoomId] = useState('')
  const [audioLevel, setAudioLevel] = useState(0)
  const [micError, setMicError] = useState('')
  const connector = useRef(createDemoAdapter())
  const streamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const active = isLiveState(state)
  const displayedSegments = active ? segments : segments.length ? segments : demoSample
  const latest = displayedSegments.at(-1)
  const sourceDisplay = autoDetect && detectedLanguage ? detectedLanguage : sourceLanguage

  useEffect(() => {
    const unsubscribeState = connector.current.onStateChange(setState)
    const unsubscribeEvent = connector.current.onEvent((event) => {
      if (event.type === 'language_detected') setDetectedLanguage(event.language)
      if (event.type === 'metrics') setMetrics((current) => applyMetrics(current, event))
      setSegments((current) => reduceAdapterEvent(event, current))
      if (event.type === 'final_translation' && voicePlayback) speak(event.text, 'en-US')
    })
    return () => { unsubscribeState(); unsubscribeEvent(); stopVoice(); streamRef.current?.getTracks().forEach((track) => track.stop()) }
  }, [voicePlayback])

  async function startMicrophone() {
    setMicError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const recorder = new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = async (event) => { if (event.data.size) connector.current.sendAudio?.(await event.data.arrayBuffer()) }
      recorder.start(250)
      await connector.current.connect({ sourceLanguage, targetLanguage })
      setRoomId(createSessionId())
      setAudioLevel(42)
    } catch { setMicError('Microphone permission is required to start a live session.') }
  }

  function stopMicrophone() { recorderRef.current?.stop(); streamRef.current?.getTracks().forEach((track) => track.stop()); recorderRef.current = null; streamRef.current = null; setAudioLevel(0) }
  async function toggleSession() { if (!active) { if (state === 'ended') setSegments([]); await startMicrophone() } else { stopMicrophone(); await connector.current.pause() } }
  async function finishSession() {
    stopMicrophone()
    await connector.current.end()
    if (!roomId || !segments.length) return

    const supabase = getSupabaseClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return

    await supabase.from('translation_sessions').insert({
      user_id: user.id,
      session_code: roomId,
      source_language: sourceDisplay,
      target_language: targetLanguage,
      status: 'ended',
      transcript: segments,
      ended_at: new Date().toISOString(),
    } as never)
  }
  async function handleAudioFile(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; setMicError(''); await connector.current.connect({ sourceLanguage, targetLanguage }); connector.current.sendAudio?.(await file.arrayBuffer()); setRoomId(createSessionId()) }
  function exportTranscript() { const text = displayedSegments.map((segment) => `[${segment.timestamp}] ${segment.source}\n${segment.translation}`).join('\n\n'); const blob = new Blob([text], { type: 'text/plain' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'hacknex-transcript.txt'; link.click(); URL.revokeObjectURL(url) }
  function swapLanguages() { setSourceLanguage(targetLanguage); setTargetLanguage(sourceLanguage) }
  const filtered = useMemo(() => displayedSegments.filter((segment) => segment.source || segment.translation), [displayedSegments])

  return <main className="app-shell"><header className="topbar"><div className="brand-lockup"><span className="brand-mark">H</span><span>HackNex <b>Live</b></span></div><nav className="main-nav" aria-label="Workspace navigation"><a className="nav-active" href="/">Live room</a><a href="/results">Results</a><a href="/status">Status</a></nav><div className="topbar-actions">{roomId && <span className="session-label">{roomId}</span>}<button className="icon-button" aria-label="Open settings" onClick={() => setShowSettings((value) => !value)}>⚙</button><div className="avatar">AM</div></div></header><section className="workspace"><div className="workspace-heading"><div><p className="eyebrow">LIVE TRANSLATION ROOM / 01</p><h1>Your words, understood.</h1><p className="subhead">A shared voice layer for meetings, classrooms, and everyday conversations.</p></div><div className="heading-actions"><div className="status-pill"><span className={`status-dot ${active ? 'pulse' : ''}`} />{active ? connectionStatus[state] : demoLabel}</div><button className="ghost-button" onClick={exportTranscript}>Export transcript ↗</button></div></div><div className="feature-strip"><div><span className="strip-icon">◉</span><span><b>Live captions</b><small>Typed adapter events</small></span></div><div><span className="strip-icon coral-icon">✦</span><span><b>Audio integration</b><small>Microphone and audio upload</small></span></div><div><span className="strip-icon">⌁</span><span><b>Measured latency</b><small>Never estimated</small></span></div><span className="powered">{active ? 'Live adapter session' : demoLabel}</span></div><div className="language-bar"><label><span>Speaking</span><select value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value)}>{languages.map((language) => <option key={language}>{language}</option>)}</select></label><button className="swap-button" onClick={swapLanguages} aria-label="Swap languages">⇄</button><label><span>Translate to</span><select value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}>{languages.filter((language) => language !== sourceLanguage).map((language) => <option key={language}>{language}</option>)}</select></label><div className="latency"><span>MEASURED</span><strong>{metricText(metrics.timeToFirstWordMs)}</strong><small>Final: {metricText(metrics.endOfSpeechToFinalMs)}</small></div><label className="toggle-label"><span>Auto-detect</span><button className={`toggle ${autoDetect ? 'on' : ''}`} onClick={() => setAutoDetect((value) => !value)} aria-label="Toggle auto-detect"><i /></button>{autoDetect && detectedLanguage && <em>{detectedLanguage}</em>}</label></div><div className="caption-grid"><section className="caption-panel source-panel"><div className="panel-label"><span><i className="language-dot teal" />{sourceDisplay}</span>{active && <span className="live-label">LIVE</span>}</div><div className="captions">{filtered.map((segment) => <p className="caption-line" key={segment.id}>{segment.source || 'Source pending…'}<small>{segment.timestamp}</small></p>)}{active && <p className="caption-line partial">{latest?.source || 'Start speaking to see live words…'}<span className="cursor" /></p>}</div><div className="panel-footer"><span>Source transcript</span><span>{active ? 'Events streaming' : demoLabel}</span></div></section><section className="caption-panel translation-panel"><div className="panel-label"><span><i className="language-dot coral" />{targetLanguage}</span>{active && <span className="stable-label">LIVE</span>}</div><div className="captions">{filtered.map((segment) => <p className="caption-line" key={segment.id}>{segment.translation || 'Translation pending…'}<small>{displayConfidence(segment.confidence)}</small></p>)}{active && <p className="caption-line partial">{latest?.translation || 'Translation will appear here…'}<span className="cursor coral-cursor" /></p>}</div><div className="panel-footer"><span>Translated output</span><span>{active && voicePlayback && supportsSpeechSynthesis() ? 'Voice playback ready' : active ? 'Voice playback unavailable' : 'Demo output'}</span></div></section></div><div className="control-row"><div className="control-meta"><span>{active ? 'Microphone active' : 'Microphone paused'}</span><span className="audio-badge">{active ? `Audio ${statusForAudio().toLowerCase()}` : 'Audio ready on start'}</span><span className="level-meter" aria-label={`Audio level ${audioLevel}%`}><i style={{ width: `${audioLevel}%` }} /></span></div><div className="controls"><label className="upload-button">Upload audio<input type="file" accept="audio/*" onChange={handleAudioFile} /></label><button className={`mic-button ${active ? 'active' : ''}`} onClick={toggleSession} aria-label={active ? 'Pause microphone' : 'Start microphone'}><span>{active ? 'Ⅱ' : '▶'}</span></button><button className="end-button" onClick={finishSession}>End session</button></div><span className="keyboard-hint">SPACE <em>to pause</em></span></div>{micError && <p className="mic-error" role="alert">{micError}</p>}<footer className="bottom-bar"><span><b>HackNex 2026</b> · Live translation for Indic languages</span><span>Private by design · <a href="/status">System status</a></span></footer></section>{showSettings && <aside className="settings-panel"><div className="panel-title"><div><p className="eyebrow">WORKSPACE SETTINGS</p><h2>Room controls</h2></div><button className="close-button" onClick={() => setShowSettings(false)}>×</button></div><label className="setting-row"><span>Voice playback</span><input type="checkbox" checked={voicePlayback} onChange={(event) => setVoicePlayback(event.target.checked)} /></label><div className="setting-row"><span>Voice API</span><b>{statusForVoice()}</b></div><div className="setting-row"><span>Adapter events</span><b>v1 connected</b></div></aside>}</main>
}
