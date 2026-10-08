import type { Metadata } from 'next'
import './globals.css'
import { AppFooter, AppHeader } from '../components/app-shell'

export const metadata: Metadata = {
  title: 'HackNex Live Translate',
  description: 'Stable, real-time translation for multilingual rooms.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><AppHeader />{children}<AppFooter /></body></html>
}
