'use client'
import { useEffect,useState } from 'react'
import Link from 'next/link'
export default function Status(){const [status,setStatus]=useState('Unknown');useEffect(()=>{fetch('/api/health').then(r=>r.json()).then(x=>setStatus(x.status)).catch(()=>setStatus('Down'))},[]);return <main className="app-shell"><header className="topbar"><strong>HackNex Status</strong><nav className="main-nav"><Link href="/">Home</Link><Link href="/app">Live room</Link><Link href="/results">Results</Link><Link className="nav-active" href="/status">Status</Link></nav></header><section className="workspace"><p className="eyebrow">SERVICE HEALTH</p><h1>System status</h1><div className="status-pill"><span className="status-dot"/>{status}</div><p className="subhead">Health is checked against the configured translation service. Unknown is honest when it is not configured.</p></section></main>
}
