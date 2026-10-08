import Link from 'next/link'
export default function Usage(){return <main className="app-shell"><section className="workspace"><p className="eyebrow">USAGE</p><h1>Minutes by language pair</h1><div className="panel"><p>Sign in to load usage_events. No usage is shown without an authenticated session.</p><Link href="/auth/login">Sign in</Link></div></section></main>}
