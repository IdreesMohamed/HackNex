import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'HackNex Live Translate',
  description: 'Stable, real-time translation for multilingual rooms.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>
}
