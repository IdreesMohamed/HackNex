'use client'

export type TranslationEvent =
  | { type: 'partial_source'; text: string; timestampMs: number }
  | { type: 'partial_translation'; text: string; timestampMs: number }
  | { type: 'committed_translation'; text: string; timestampMs: number; confidence?: number }
  | { type: 'final_translation'; text: string; timestampMs: number; confidence?: number }
  | { type: 'language_detected'; language: string; timestampMs: number }
  | { type: 'metrics'; timeToFirstWordMs?: number; endOfSpeechToFinalMs?: number; timestampMs: number }
  | { type: 'error'; message: string; timestampMs: number }

export type TranslationClientOptions = { sourceLanguage: string; targetLanguage: string; glossary?: string[] }

export class TranslationClient {
  private socket?: WebSocket
  private listeners = new Set<(event: TranslationEvent) => void>()
  private retry = 0
  private closed = false
  onEvent(listener: (event: TranslationEvent) => void) { this.listeners.add(listener); return () => this.listeners.delete(listener) }
  async connect(options: TranslationClientOptions) {
    this.closed = false
    if (process.env.NEXT_PUBLIC_USE_MOCK === 'true') return
    const tokenResponse = await fetch('/api/translation/token', { method: 'POST' })
    if (!tokenResponse.ok) throw new Error('Translation service token unavailable')
    const { token } = await tokenResponse.json()
    const url = process.env.NEXT_PUBLIC_TRANSLATION_WS_URL
    if (!url) throw new Error('Translation service is not configured')
    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(`${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`)
      this.socket = socket
      socket.onopen = () => { this.retry = 0; socket.send(JSON.stringify({ type: 'connect', ...options })); resolve() }
      socket.onmessage = (message) => { try { const event = JSON.parse(message.data) as TranslationEvent; this.listeners.forEach((listener) => listener(event)) } catch { this.emit({ type: 'error', message: 'Invalid translation event', timestampMs: Date.now() }) } }
      socket.onerror = () => reject(new Error('Unable to connect to translation service'))
    })
  }
  sendAudio(audio: ArrayBuffer) { if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(audio) }
  pause() { this.socket?.send(JSON.stringify({ type: 'pause' })) }
  resume() { this.socket?.send(JSON.stringify({ type: 'resume' })) }
  end() { this.closed = true; this.socket?.send(JSON.stringify({ type: 'end' })); this.socket?.close() }
  private emit(event: TranslationEvent) { this.listeners.forEach((listener) => listener(event)) }
}

export const createTranslationClient = () => new TranslationClient()
export const eventContract = ['partial_source', 'partial_translation', 'committed_translation', 'final_translation', 'language_detected', 'metrics', 'error'] as const
export const isTranslationEvent = (value: unknown): value is TranslationEvent => typeof value === 'object' && value !== null && 'type' in value

export async function fetchHealth() {
  const response = await fetch('/api/health', { cache: 'no-store' })
  return response.json() as Promise<{ state: 'Operational' | 'Degraded' | 'Down' | 'Unknown'; responseTimeMs?: number; version?: string }>
}

export function downloadBlob(name: string, content: string, type: string) { const url = URL.createObjectURL(new Blob([content], { type })); const link = document.createElement('a'); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url) }

export function toCsv(rows: Record<string, unknown>[]) { if (!rows.length) return ''; const keys = Object.keys(rows[0]); return [keys.join(','), ...rows.map((row) => keys.map((key) => JSON.stringify(row[key] ?? '')).join(','))].join('\n') }

export function formatMeasured(value?: number | null) { return value == null ? 'Not measured' : `${Math.round(value)} ms` }

export function mockEvents() { return [{ type: 'language_detected', language: 'Tamil', timestampMs: Date.now() }, { type: 'partial_source', text: 'வணக்கம்', timestampMs: Date.now() }, { type: 'partial_translation', text: 'Hello', timestampMs: Date.now() }, { type: 'committed_translation', text: 'Hello', timestampMs: Date.now() }, { type: 'final_translation', text: 'Hello', timestampMs: Date.now() }] as TranslationEvent[] }

export function backoff(attempt: number) { return Math.min(1000 * 2 ** attempt, 15000) }
