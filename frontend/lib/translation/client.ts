export type TranslationEvent =
  | { type: 'partial_source'; text: string; timestampMs: number }
  | { type: 'partial_translation'; text: string; timestampMs: number }
  | { type: 'committed_translation'; text: string; timestampMs: number; confidence?: number }
  | { type: 'final_translation'; text: string; timestampMs: number; confidence?: number }
  | { type: 'language_detected'; language: string; timestampMs: number }
  | { type: 'metrics'; timeToFirstWordMs?: number; endOfSpeechToFinalMs?: number; timestampMs: number }
  | { type: 'error'; message: string; timestampMs: number }

export type TranslationSession = { sourceLanguage: string; targetLanguage: string; glossary: string[]; autoDetect: boolean }
export type TranslationAdapter = { connect(session: TranslationSession): Promise<void>; sendAudio(audio: ArrayBuffer): void; pause(): Promise<void>; end(): Promise<void>; onEvent(cb: (event: TranslationEvent) => void): () => void }

class MockAdapter implements TranslationAdapter {
  private listeners = new Set<(event: TranslationEvent) => void>()
  private timer?: ReturnType<typeof setTimeout>
  private started = 0
  async connect(session: TranslationSession) { this.started = Date.now(); this.emit({ type: 'language_detected', language: session.sourceLanguage, timestampMs: Date.now() }); this.timer = setTimeout(() => { const now = Date.now(); this.emit({ type: 'partial_source', text: 'வணக்கம், அனைவரும் எப்படி இருக்கிறீர்கள்?', timestampMs: now }); this.emit({ type: 'partial_translation', text: 'Hello, how is everyone?', timestampMs: now + 120 }); this.emit({ type: 'committed_translation', text: 'Hello, how is everyone?', timestampMs: now + 480, confidence: 0.98 }); this.emit({ type: 'final_translation', text: 'Hello, how is everyone?', timestampMs: now + 620, confidence: 0.98 }); this.emit({ type: 'metrics', timeToFirstWordMs: now - this.started, endOfSpeechToFinalMs: 620, timestampMs: now + 620 }) }, 900) }
  sendAudio(_audio: ArrayBuffer) {}
  async pause() { if (this.timer) clearTimeout(this.timer) }
  async end() { if (this.timer) clearTimeout(this.timer) }
  onEvent(cb: (event: TranslationEvent) => void) { this.listeners.add(cb); return () => this.listeners.delete(cb) }
  private emit(event: TranslationEvent) { this.listeners.forEach((listener) => listener(event)) }
}

export function createTranslationAdapter(): TranslationAdapter { return new MockAdapter() }
export const supportedLanguages = ['Tamil', 'Hindi', 'English', 'Kannada', 'Telugu', 'Malayalam']
export function formatMetric(value?: number) { return value == null ? 'Collecting' : `${Math.round(value)} ms` }
export function isMockEnabled() { return process.env.NEXT_PUBLIC_USE_MOCK === 'true' }
export function formatEventTime(ms: number) { return new Date(ms).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' }) }
export function audioFileIsWav(file: File) { return file.type === 'audio/wav' || file.type === 'audio/x-wav' || file.name.toLowerCase().endsWith('.wav') }
export function createRoomId() { return `HN-${crypto.randomUUID().slice(0, 8).toUpperCase()}` }
export function downloadFile(name: string, content: string, type: string) { const url = URL.createObjectURL(new Blob([content], { type })); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url) }
export function seconds(ms?: number) { return ms == null ? 'Not measured' : `${(ms / 1000).toFixed(2)}s` }
export function csvEscape(value: unknown) { return `"${String(value ?? 'Not measured').replaceAll('"', '""')}"` }
