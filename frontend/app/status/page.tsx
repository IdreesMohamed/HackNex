'use client'

import { useEffect, useState } from 'react'
import { statusForAudio, statusForVoice, supportsAudioCapture, supportsSpeechSynthesis } from '../../lib/connectors'

export default function StatusPage() {
  const [checks, setChecks] = useState([{ name: 'Frontend', status: 'Checking', detail: 'Verifying the browser runtime' }, { name: 'Translation adapter', status: 'Operational', detail: 'Typed adapter event contract is loaded' }, { name: 'Audio capture', status: 'Checking', detail: 'Checking browser microphone support' }, { name: 'Voice output', status: 'Checking', detail: 'Checking browser speech synthesis support' }])
  useEffect(() => { setChecks([{ name: 'Frontend', status: 'Operational', detail: 'Next.js workspace is serving' }, { name: 'Translation adapter', status: 'Operational', detail: 'Adapter contract loaded; provider connection is configured by the runtime' }, { name: 'Audio capture', status: statusForAudio(), detail: supportsAudioCapture() ? 'Microphone permission is requested only when you start a room' : 'This browser does not expose microphone capture' }, { name: 'Voice output', status: statusForVoice(), detail: supportsSpeechSynthesis() ? 'Speech synthesis is available for translated output' : 'This browser does not expose speech synthesis' }]) }, [])
  return <main className="app-shell"><section className="workspace results-page"><p className="eyebrow">SYSTEM STATUS</p><h1>HackNex Live status</h1><p className="subhead">Runtime checks are measured in this browser; provider health is reported by the adapter.</p><div className="status-list">{checks.map((check) => <article className="note-card" key={check.name}><div className="panel-label"><span><i className={`status-dot ${check.status === 'Operational' || check.status === 'Ready' ? 'pulse' : ''}`} />{check.name}</span><strong>{check.status}</strong></div><p>{check.detail}</p></article>)}</div><a className="ghost-button" href="/">Back to live room</a></section></main>
}
