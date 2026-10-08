'use client'

import Link from 'next/link'

const stats = [
  ['04', 'supported languages'],
  ['02', 'honest latency metrics'],
  ['∞', 'conversations to understand'],
]

const faqs = [
  ['Is this a live translation demo?', 'The landing page preview is labeled as demo content. Live sessions in the room only show events received from the configured translation adapter.'],
  ['How do you measure speed?', 'We report time to first word and end of speech to final only when the engine sends real timestamps. Otherwise the interface stays honest with Collecting.'],
  ['Which languages are supported?', 'English, Hindi, Tamil, and Malayalam are supported in the current room experience, including Indic-script captions.'],
]

export default function Landing() {
  return <main className="landing-page">
    <header className="topbar landing-nav">
      <Link className="brand-lockup" href="/"><span className="brand-mark">H</span><span>HackNex <b>Live</b></span></Link>
      <nav className="main-nav" aria-label="Main navigation"><Link className="nav-active" href="/">Home</Link><Link href="/results">Results</Link><Link href="/compare">Compare</Link><Link href="/status">Status</Link></nav>
      <div className="topbar-actions"><Link className="ghost-button" href="/auth/login">Sign in</Link><Link className="primary-button compact" href="/app">Open room <span aria-hidden="true">↗</span></Link></div>
    </header>
    <section className="landing-hero">
      <div className="hero-copy"><p className="eyebrow"><i className="dot" /> REALTIME TRANSLATION / HNX-01</p><h1>Make space<br /><em>for every voice.</em></h1><p className="hero-lede">A calm, measurable translation layer for rooms where understanding matters more than speaking louder.</p><div className="heading-actions"><Link className="primary-button" href="/app">Enter the live room <span aria-hidden="true">→</span></Link><Link className="text-link" href="#how-it-works">See how it works <span aria-hidden="true">↓</span></Link></div><div className="hero-proof"><span className="proof-avatar">H</span><span><strong>Built for real conversations</strong><small>Stable captions · measured latency · privacy first</small></span></div></div>
      <div className="hero-visual" aria-label="Translation preview"><div className="visual-topline"><span className="live-badge active"><i className="dot" /> LIVE PREVIEW</span><span className="mono">00:18</span></div><div className="visual-language"><span>Tamil <small>தமிழ்</small></span><span className="visual-arrow">→</span><span>English <small>EN</small></span></div><div className="visual-caption"><small>தமிழ் · SOURCE</small><p>நாளை சந்திப்போம்</p><small>ENGLISH · TRANSLATION</small><p className="translated">We&apos;ll meet tomorrow<span className="caret" /></p></div><div className="visual-footer"><span><i className="stable-dot" /> Stable prefix</span><span className="mono">TTFW 284 ms</span></div></div>
    </section>
    <section className="stat-strip" aria-label="Product facts">{stats.map(([value, label]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}</section>
    <section className="landing-section" id="how-it-works"><div className="section-intro"><p className="eyebrow">THE FLOW / 01—03</p><h2>From voice<br /><em>to understanding.</em></h2><p>Every layer is visible. Every measurement is earned. No invented confidence, no mystery numbers.</p></div><div className="flow-grid"><article><span className="step-number">01</span><span className="step-icon">◉</span><h3>Speak naturally</h3><p>Capture a real conversation with microphone input or upload a WAV recording.</p></article><article><span className="step-number">02</span><span className="step-icon">⌁</span><h3>Watch words settle</h3><p>Provisional captions stay dimmed while committed words become solid and readable.</p></article><article><span className="step-number">03</span><span className="step-icon">✦</span><h3>Measure what matters</h3><p>See first-word speed, finalization, confidence, and stability only when measured.</p></article></div></section>
    <section className="landing-section language-section"><div><p className="eyebrow">MADE FOR MULTILINGUAL ROOMS</p><h2>Four languages.<br /><em>One clear room.</em></h2></div><div className="language-list"><div><strong>English</strong><span>English</span></div><div><strong>Hindi</strong><span>हिन्दी</span></div><div><strong>Tamil</strong><span>தமிழ்</span></div><div><strong>Malayalam</strong><span>മലയാളം</span></div></div></section>
    <section className="landing-section pricing-section"><div className="section-intro"><p className="eyebrow">SIMPLE BY DESIGN</p><h2>Start with<br /><em>what you need.</em></h2></div><div className="pricing-grid"><article className="pricing-card featured"><span className="pricing-kicker">FOR INDIVIDUALS</span><h3>Free</h3><p>For trying the room and understanding the signal.</p><strong>Coming soon</strong><Link href="/app" className="secondary-button">Explore the room →</Link></article><article className="pricing-card"><span className="pricing-kicker">FOR SERIOUS WORK</span><h3>Pro</h3><p>Longer sessions, searchable history, and deeper review.</p><strong>Coming soon</strong><button className="secondary-button" type="button">Join the waitlist</button></article><article className="pricing-card"><span className="pricing-kicker">FOR TEAMS</span><h3>Team</h3><p>Shared rooms and usage visibility for every voice.</p><strong>Coming soon</strong><button className="secondary-button" type="button">Talk to us</button></article></div></section>
    <section className="landing-section faq-section"><div className="section-intro"><p className="eyebrow">QUESTIONS / ANSWERS</p><h2>Clear answers<br /><em>before you begin.</em></h2></div><div className="faq-list">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<span>+</span></summary><p>{answer}</p></details>)}</div></section>
    <footer className="landing-footer"><Link className="brand-lockup" href="/"><span className="brand-mark">H</span><span>HackNex <b>Live</b></span></Link><span>Measured translation for more human rooms.</span><div><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/status">System status</Link></div></footer>
  </main>
}
