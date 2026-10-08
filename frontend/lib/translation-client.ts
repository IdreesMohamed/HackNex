export type TranslationEvent =
  | { type: 'partial_source' | 'partial_translation' | 'committed_translation' | 'final_translation'; text: string; timestamp: number }
  | { type: 'language_detected'; language: string }
  | { type: 'metrics'; timeToFirstWordMs?: number; endOfSpeechToFinalMs?: number }
  | { type: 'error'; message: string }

export type TranslationClient = {
  connect: () => Promise<void>
  send: (chunk: ArrayBuffer) => void
  close: () => void
  subscribe: (listener: (event: TranslationEvent) => void) => () => void
}

export function createTranslationClient(options: { source: string; target: string; glossary: Record<string, string>; token?: string }): TranslationClient {
  const listeners = new Set<(event: TranslationEvent) => void>()
  const apiUrl = process.env.NEXT_PUBLIC_API_URL
  const socketUrl = apiUrl ? `${apiUrl.replace(/\/$/, '').replace(/^https:/, 'wss:').replace(/^http:/, 'ws:')}/ws/translate` : undefined
  let socket: WebSocket | undefined
  const emit = (event: TranslationEvent) => listeners.forEach((listener) => listener(event))
  return {
    async connect() {
      if (!socketUrl || process.env.NEXT_PUBLIC_TRANSLATION_DEMO === 'true') {
        emit({ type: 'language_detected', language: options.source })
        return
      }
      socket = new WebSocket(`${socketUrl}?source=${encodeURIComponent(options.source)}&target=${encodeURIComponent(options.target)}`)
      await new Promise<void>((resolve, reject) => {
        socket?.addEventListener('open', () => resolve(), { once: true })
        socket?.addEventListener('error', () => reject(new Error('Translation service unavailable')), { once: true })
      })
    },
    send(chunk) {
      if (socket?.readyState === WebSocket.OPEN) socket.send(chunk)
    },
    close() { socket?.close(); socket = undefined },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener) },
  }
}

export function commitPrefix(previous: string, incoming: string) {
  if (!previous) return incoming
  if (incoming.startsWith(previous)) return incoming
  const words = incoming.split(/(\s+)/)
  const previousWords = previous.split(/(\s+)/)
  let index = 0
  while (index < previousWords.length && previousWords[index] === words[index]) index += 1
  return previousWords.slice(0, index).join('') + words.slice(index).join('')
}

export function measureSession(startedAt: number, speechEndedAt: number, finalAt: number) {
  return { timeToFirstWordMs: Math.max(0, speechEndedAt - startedAt), endOfSpeechToFinalMs: Math.max(0, finalAt - speechEndedAt) }
}
