export type ConnectionState = 'idle' | 'connecting' | 'listening' | 'degraded' | 'ended' | 'error'

export type AdapterEvent =
  | { type: 'partial_source'; text: string; timestampMs: number }
  | { type: 'partial_translation'; text: string; timestampMs: number }
  | { type: 'committed_translation'; text: string; timestampMs: number; confidence?: number }
  | { type: 'final_translation'; text: string; timestampMs: number; confidence?: number }
  | { type: 'language_detected'; language: string; timestampMs: number }
  | { type: 'metrics'; timeToFirstWordMs?: number; endOfSpeechToFinalMs?: number; timestampMs: number }

export type CaptionSegment = { id: string; source: string; translation: string; timestamp: string; confidence?: number; isPartial?: boolean }
export type MeasuredMetrics = { timeToFirstWordMs?: number; endOfSpeechToFinalMs?: number }

export interface TranslationConnector {
  connect(session: { sourceLanguage: string; targetLanguage: string }): Promise<void>
  pause(): Promise<void>
  resume(): Promise<void>
  end(): Promise<void>
  sendAudio?(audioChunk: ArrayBuffer): void
  onEvent(callback: (event: AdapterEvent) => void): () => void
  onStateChange(callback: (state: ConnectionState) => void): () => void
}

export const demoLabel = 'Demo recording'
export const demoSample: CaptionSegment[] = [
  { id: 'demo-1', source: 'இன்று நாம் மொழிகளுக்கு இடையே உள்ள தடைகளை உடைக்கிறோம்.', translation: 'Today, we are breaking the barriers between languages.', timestamp: '00:02', confidence: 0.99 },
  { id: 'demo-2', source: 'ஒவ்வொருவரும் தங்கள் குரலில் பங்கேற்கலாம்.', translation: 'Everyone can participate in their own voice.', timestamp: '00:08', confidence: 0.97 },
]
export const connectionStatus: Record<ConnectionState, string> = { idle: 'Paused', connecting: 'Connecting', listening: 'Listening live', degraded: 'Degraded', ended: 'Session ended', error: 'Connection error' }
export const languageCode: Record<string, string> = { Tamil: 'ta-IN', Hindi: 'hi-IN', English: 'en-US', Malayalam: 'ml-IN' }

export class DemoTranslationConnector implements TranslationConnector {
  private eventListeners = new Set<(event: AdapterEvent) => void>()
  private stateListeners = new Set<(state: ConnectionState) => void>()
  private timer?: ReturnType<typeof setTimeout>
  private stopped = false
  async connect(_session: { sourceLanguage: string; targetLanguage: string }) {
    this.stopped = false
    this.emitState('connecting')
    await new Promise((resolve) => setTimeout(resolve, 500))
    if (this.stopped) return
    this.emitState('listening')
    const started = performance.now()
    this.timer = setTimeout(() => {
      if (this.stopped) return
      const now = performance.now()
      this.emit({ type: 'language_detected', language: 'Tamil', timestampMs: Date.now() })
      this.emit({ type: 'partial_source', text: 'வணக்கம், அனைவரும் எப்படி இருக்கிறீர்கள்?', timestampMs: Date.now() })
      this.emit({ type: 'partial_translation', text: 'Hello, how is everyone?', timestampMs: Date.now() })
      this.emit({ type: 'committed_translation', text: 'Hello, how is everyone?', timestampMs: Date.now(), confidence: 0.98 })
      this.emit({ type: 'final_translation', text: 'Hello, how is everyone?', timestampMs: Date.now(), confidence: 0.98 })
      this.emit({ type: 'metrics', timeToFirstWordMs: Math.round(now - started), endOfSpeechToFinalMs: 180, timestampMs: Date.now() })
    }, 1100)
  }
  sendAudio(_audioChunk: ArrayBuffer) {}
  async pause() { this.emitState('idle') }
  async resume() { this.emitState('listening') }
  async end() { this.stopped = true; if (this.timer) clearTimeout(this.timer); this.emitState('ended') }
  onEvent(callback: (event: AdapterEvent) => void) { this.eventListeners.add(callback); return () => this.eventListeners.delete(callback) }
  onStateChange(callback: (state: ConnectionState) => void) { this.stateListeners.add(callback); return () => this.stateListeners.delete(callback) }
  private emit(event: AdapterEvent) { this.eventListeners.forEach((listener) => listener(event)) }
  private emitState(state: ConnectionState) { this.stateListeners.forEach((listener) => listener(state)) }
}

export function formatTimestamp(timestampMs: number) { return new Date(timestampMs).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' }) }
export function reduceAdapterEvent(event: AdapterEvent, previous: CaptionSegment[]) {
  if (event.type === 'metrics' || event.type === 'language_detected') return previous
  const current = previous.at(-1)
  if (event.type === 'partial_source') return current?.isPartial ? [...previous.slice(0, -1), { ...current, source: event.text, timestamp: formatTimestamp(event.timestampMs) }] : [...previous, { id: crypto.randomUUID(), source: event.text, translation: '', timestamp: formatTimestamp(event.timestampMs), isPartial: true }]
  if (event.type === 'partial_translation') return current?.isPartial ? [...previous.slice(0, -1), { ...current, translation: event.text }] : previous
  return current?.isPartial ? [...previous.slice(0, -1), { ...current, translation: event.text, confidence: event.confidence, isPartial: event.type !== 'final_translation' }] : [...previous, { id: crypto.randomUUID(), source: '', translation: event.text, timestamp: formatTimestamp(event.timestampMs), confidence: event.confidence }]
}

export function applyMetrics(current: MeasuredMetrics, event: AdapterEvent): MeasuredMetrics { return event.type === 'metrics' ? { timeToFirstWordMs: event.timeToFirstWordMs ?? current.timeToFirstWordMs, endOfSpeechToFinalMs: event.endOfSpeechToFinalMs ?? current.endOfSpeechToFinalMs } : current }
export function createSessionId() { return `HN-${crypto.randomUUID().slice(0, 8).toUpperCase()}` }
export function isLiveState(state: ConnectionState) { return state === 'listening' || state === 'connecting' }
export function metricText(value?: number) { return value == null ? 'Collecting' : `${Math.round(value)} ms` }
export function supportsAudioCapture() { return typeof navigator !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia) }
export function supportsSpeechSynthesis() { return typeof window !== 'undefined' && 'speechSynthesis' in window }
export function speak(text: string, language: string) { if (!supportsSpeechSynthesis()) return false; const utterance = new SpeechSynthesisUtterance(text); utterance.lang = language; window.speechSynthesis.speak(utterance); return true }
export function stopVoice() { if (supportsSpeechSynthesis()) window.speechSynthesis.cancel() }
export const createDemoAdapter = () => new DemoTranslationConnector()
export const eventContract = ['partial_source', 'partial_translation', 'committed_translation', 'final_translation', 'language_detected', 'metrics'] as const
export function noResultsLabel() { return 'No results yet' }
export function errorMessage(error: unknown) { return error instanceof Error ? error.message : 'Something went wrong.' }
export function serializeSession(segments: CaptionSegment[]) { return JSON.stringify(segments) }
export function parseSession(value: string | null): CaptionSegment[] { try { return value ? JSON.parse(value) : [] } catch { return [] } }
export function validDirection(source: string, target: string) { return source !== target }
export function isSupportedAudio(file: File) { return file.type.startsWith('audio/') && file.size <= 25 * 1024 * 1024 }
export function statusForAudio() { return supportsAudioCapture() ? 'Ready' : 'Unavailable' }
export function statusForVoice() { return supportsSpeechSynthesis() ? 'Ready' : 'Unavailable' }
export function displayConfidence(value?: number) { return value == null ? 'Not measured' : `${Math.round(value * 100)}% confidence` }
export function cleanSegments(segments: CaptionSegment[]) { return segments.filter((segment) => segment.source || segment.translation) }
export function emptyMetrics(): MeasuredMetrics { return {} }
