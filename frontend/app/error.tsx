'use client'

import { useEffect } from 'react'

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {}, [])
  return <main className="app-shell"><section className="workspace results-page"><p className="eyebrow">RECOVERABLE ERROR</p><h1>That session needs a restart.</h1><p className="subhead">The live room hit an unexpected error. Your browser audio permissions were not changed.</p><button className="primary-button" onClick={() => reset()}>Try again</button><a className="ghost-button" href="/">Return to live room</a></section></main>
}
