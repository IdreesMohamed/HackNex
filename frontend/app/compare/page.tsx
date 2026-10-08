'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

type Replay = { name?: string; source?: string; baseline?: { captions?: { timeMs: number; text: string }[]; metrics?: Record<string, string | number> }; ours?: { captions?: { timeMs: number; text: string }[]; metrics?: Record<string, string | number> } }

export default function Compare() {
  const [files, setFiles] = useState<string[]>([])
  const [selected, setSelected] = useState<Replay | null>(null)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  useEffect(() => { fetch('/api/compare').then((r) => r.json()).then((x) => setFiles(x.files ?? [])).catch(() => setFiles([])) }, [])
  useEffect(() => { if (!playing || !selected) return; const id = window.setInterval(() => setTime((value) => value + 250), 250); return () => window.clearInterval(id) }, [playing, selected])
  const current = (items: Replay['baseline'] = {}) => items.captions?.filter((caption) => caption.timeMs <= time).at(-1)?.text ?? 'Waiting for replay…'
  return <main className="app-shell"><header className="topbar"><Link className="brand-lockup" href="/"><span className="brand-mark">H</span><span>HackNex <b>Live</b></span></Link><nav className="main-nav" aria-label="Main navigation"><Link href="/app">Live room</Link><Link className="nav-active" href="/compare">Compare</Link><Link href="/results">Results</Link><Link href="/status">Status</Link></nav></header><section className="workspace"><p className="eyebrow">REPLAY LAB / REAL-TIME</p><h1>Baseline vs Ours</h1><p className="subhead">Replay a selected recording at its measured speed. No files means no invented comparison.</p>{files.length === 0 ? <div className="panel empty-state"><h2>No recordings yet</h2><p>Add JSON files to <code>/public/compare/</code> to enable side-by-side replay.</p></div> : <><div className="control-row"><select aria-label="Recording" onChange={async (event) => setSelected(await fetch(`/compare/${event.target.value}`).then((response) => response.json()))}><option>Select a recording</option>{files.map((file) => <option key={file}>{file}</option>)}</select><button className="primary-button" disabled={!selected} onClick={() => { setTime(0); setPlaying(true) }}>{playing ? 'Playing at real time' : 'Play replay'}</button></div>{selected && <div className="compare-grid"><CompareColumn title="Baseline" text={current(selected.baseline)} /><CompareColumn title="Ours" text={current(selected.ours)} /></div>}</>}</section></main>
}
function CompareColumn({ title, text }: { title: string; text: string }) { return <section className="panel caption-panel"><header className="panel-header"><h2>{title}</h2><span className="chip">Replay</span></header><p className="caption-text">{text}</p><div className="metric-list"><div><span>Time to first word</span><b>Not measured</b></div><div><span>End of speech → final</span><b>Not measured</b></div><div><span>Late rewrites</span><b>Not measured</b></div></div></section> }
