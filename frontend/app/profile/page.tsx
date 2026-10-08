import Link from 'next/link'
export default function Profile(){return <main className="app-shell"><section className="workspace"><p className="eyebrow">ACCOUNT</p><h1>Profile</h1><div className="panel"><p>Sign in to view and update your profile.</p><Link className="primary-button" href="/auth/login">Sign in</Link></div></section></main>}
