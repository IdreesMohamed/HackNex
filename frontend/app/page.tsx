'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { DemoTranslationConnector, type CaptionSegment, type ConnectionState } from '../lib/connectors'

const languages = [
  { value: 'Tamil', native: 'தமிழ்', code: 'TA' },
  { value: 'Hindi', native: 'हिन्दी', code: 'HI' },
  { value: 'English', native: 'English', code: 'EN' },
  { value: 'Malayalam', native: 'മലയാളം', code: 'ML' },
]

const initialSegments: CaptionSegment[] = [
  { id: '1', source: 'இன்று நாம் மொழிகளுக்கு இடையே உள்ள தடைகளை உடைக்கிறோம்.', translation: 'Today, we are breaking the barriers between languages.', timestamp: '00:02', confidence: 0.99 },
  { id: '2', source: 'ஒவ்வொருவரும் தங்கள் குரலில் பங்கேற்கலாம்.', translation: 'Everyone can participate in their own voice.', timestamp: '00:08', confidence: 0.97 },
]

function statusCopy(state: ConnectionState) {
  return { idle: 'Ready to translate', connecting: 'Connecting to speech service', listening: 'Listening live', degraded: 'Translation degraded', ended: 'Session ended', error: 'Connection error' }[state]
}

export default function Home() {
  const [sourceLanguage, setSourceLanguage] = useState('Tamil')
  const [targetLanguage, setTargetLanguage] = useState('English')
  const [state, setState] = useState<ConnectionState>('listening')
  const [segments, setSegments] = useState(initialSegments)
  const [showSetup, setShowSetup] = useState(false)
  const connector = useRef(new DemoTranslationConnector())

  useEffect(() => {
    const unsubscribeState = connector.current.onStateChange(setState)
    const unsubscribeCaption = connector.current.onCaption((segment) => setSegments((current) => [...current, segment]))
    return () => { unsubscribeState(); unsubscribeCaption() }
  }, [])

  const isLive = state === 'listening' || state === 'connecting'
  const latest = useMemo(() => segments[segments.length - 1], [segments])

  async function toggleSession() {
    if (isLive) await connector.current.pause()
    else if (state === 'ended') { setSegments([]); await connector.current.connect({ sourceLanguage, targetLanguage }) }
    else await connector.current.resume()
  }

  async function finishSession() { await connector.current.end() }

  function swapLanguages() { setSourceLanguage(targetLanguage); setTargetLanguage(sourceLanguage) }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup"><span className="brand-mark">H</span><span>HackNex <b>Live</b></span></div>
        <div className="topbar-actions">
          <span className="session-label">SESSION <strong>HN-2048</strong></span>
          <button className="icon-button" aria-label="Open settings" onClick={() => setShowSetup((current) => !current)}>•••</button>
          <div className="avatar" aria-label="Account">AM</div>
        </div>
      </header>

      <section className="workspace">
        <div className="workspace-heading">
          <div><p className="eyebrow">LIVE TRANSLATION ROOM</p><h1>Your words, understood.</h1></div>
          <div className="status-pill"><span className={`status-dot ${isLive ? 'pulse' : ''}`} />{statusCopy(state)}</div>
        </div>

        <div className="language-bar">
          <label><span>Speaking</span><select value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value)}>{languages.map((language) => <option key={language.value} value={language.value}>{language.value} · {language.native}</option>)}</select></label>
          <button className="swap-button" onClick={swapLanguages} aria-label="Swap languages">⇄</button>
          <label><span>Translate to</span><select value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}>{languages.map((language) => <option key={language.value} value={language.value}>{language.value} · {language.native}</option>)}</select></label>
          <div className="latency"><span>LATENCY</span><strong>0.8s</strong></div>
        </div>

        <div className="caption-grid">
          <section className="caption-panel source-panel"><div className="panel-label"><span><i className="language-dot teal" />{sourceLanguage}</span><span className="live-label">LIVE</span></div><div className="captions">{segments.map((segment) => <p className="caption-line" key={segment.id}>{segment.source}</p>)}{isLive && <p className="caption-line partial">{latest?.source ?? 'Start speaking to see your words here…'}<span className="cursor" /></p>}</div><div className="panel-footer"><span>Source transcript</span><span>Auto-detect off</span></div></section>
          <section className="caption-panel translation-panel"><div className="panel-label"><span><i className="language-dot coral" />{targetLanguage}</span><span className="stable-label">STABLE</span></div><div className="captions">{segments.map((segment) => <p className="caption-line" key={segment.id}>{segment.translation}</p>)}{isLive && <p className="caption-line partial">{latest?.translation ?? 'Translation will appear here…'}<span className="cursor coral-cursor" /></p>}</div><div className="panel-footer"><span>Translated output</span><span>Powered by Sarvam</span></div></section>
        </div>

        <div className="control-row"><div className="control-meta"><span className="mic-wave"><i /><i /><i /><i /><i /></span><span>{isLive ? 'Microphone active' : 'Microphone paused'}</span></div><div className="controls"><button className={`mic-button ${isLive ? 'active' : ''}`} onClick={toggleSession} aria-label={isLive ? 'Pause microphone' : 'Resume microphone'}><span>{isLive ? 'Ⅱ' : '▶'}</span></button><button className="end-button" onClick={finishSession}>End session</button></div><span className="keyboard-hint">SPACE <em>to pause</em></span></div>

        {showSetup && <aside className="setup-card"><p className="eyebrow">SESSION CONTROLS</p><h2>Room settings</h2><p>Connector status is ready. The live UI is wired to a replaceable translation connector.</p><div className="provider-row"><span className="provider-icon">S</span><span><strong>Sarvam realtime</strong><small>Primary provider</small></span><span className="connected">Connected</span></div></aside>}

        <footer className="bottom-bar"><span><b>HackNex 2026</b> · Live translation for Indic languages</span><span>Built for every voice <span className="footer-mark">+</span></span></footer>
      </section>
    </main>
  )
}
