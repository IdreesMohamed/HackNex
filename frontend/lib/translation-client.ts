export type TranslationEvent =
  | { type: 'partial_source'; text: string }
  | { type: 'partial_translation'; text: string }
  | { type: 'committed_translation'; text: string; timestamp: number }
  | { type: 'final_translation'; text: string; timestamp: number }
  | { type: 'language_detected'; language: string }
  | { type: 'metrics'; timeToFirstWordMs: number; endOfSpeechToFinalMs: number }
  | { type: 'error'; message: string }

export type TranslationConnection = {
  send: (chunk: ArrayBuffer) => void
  close: () => void
  subscribe: (listener: (event: TranslationEvent) => void) => () => void
}

export function connectTranslation(options: { source: string; target: string; glossary: Record<string, string>; token?: string }): TranslationConnection {
  const listeners = new Set<(event: TranslationEvent) => void>()
  const emit = (event: TranslationEvent) => listeners.forEach((listener) => listener(event))
  let socket: WebSocket | undefined
  const url = process.env.NEXT_PUBLIC_TRANSLATION_WS_URL
  if (url && typeof WebSocket !== 'undefined') {
    try {
      socket = new WebSocket(`${url}?source=${encodeURIComponent(options.source)}&target=${encodeURIComponent(options.target)}`)
      socket.onmessage = (message) => { try { emit(JSON.parse(message.data) as TranslationEvent) } catch { emit({ type: 'error', message: 'Received an invalid translation event.' }) } }
      socket.onerror = () => emit({ type: 'error', message: 'Translation service unavailable. Showing demo mode.' })
    } catch { emit({ type: 'error', message: 'Translation service unavailable. Showing demo mode.' }) }
  }
  return {
    send(chunk) { if (socket?.readyState === WebSocket.OPEN) socket.send(chunk) },
    close() { socket?.close() },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener) },
  }
}

export const demoEvents: TranslationEvent[] = [
  { type: 'language_detected', language: 'Tamil' },
  { type: 'partial_source', text: 'இன்று நாம் மொழிகளுக்கு இடையே உள்ள தடைகளை உடைக்கிறோம்.' },
  { type: 'partial_translation', text: 'Today, we are breaking the barriers between languages.' },
  { type: 'committed_translation', text: 'Today, we are breaking the barriers between languages.', timestamp: 4200 },
  { type: 'metrics', timeToFirstWordMs: 820, endOfSpeechToFinalMs: 610 },
]

export const supportedLanguages = ['English', 'Hindi', 'Tamil', 'Malayalam'] as const
export type SupportedLanguage = typeof supportedLanguages[number]

export function isSupportedPair(source: string, target: string) { return source !== target && supportedLanguages.includes(source as SupportedLanguage) && supportedLanguages.includes(target as SupportedLanguage) }
export function commitPrefix(committed: string, incoming: string) { return incoming.startsWith(committed) ? incoming : committed }
