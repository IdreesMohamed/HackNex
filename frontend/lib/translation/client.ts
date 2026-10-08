export type TranslationEvent =
  | { type: 'partial_source'; text: string; timestampMs: number }
  | { type: 'final_source'; text: string; timestampMs: number }
  | { type: 'partial_translation'; text: string; timestampMs: number }
  | { type: 'committed_translation'; text: string; timestampMs: number; confidence?: number }
  | { type: 'final_translation'; text: string; timestampMs: number; confidence?: number }
  | { type: 'language_detected'; language: string; timestampMs: number }
  | { type: 'metrics'; timeToFirstWordMs?: number; endOfSpeechToFinalMs?: number; timestampMs: number }
  | { type: 'error'; message: string; timestampMs: number }

export type TranslationSession = { sourceLanguage: string; targetLanguage: string; glossary: string[]; autoDetect: boolean }
export type TranslationAdapter = { connect(session: TranslationSession): Promise<void>; sendAudio(audio: ArrayBuffer): void; attachMicrophone?(stream: MediaStream): void; pause(): Promise<void>; resume?(): Promise<void>; end(): Promise<void>; onEvent(cb: (event: TranslationEvent) => void): () => void }

class BackendAdapter implements TranslationAdapter {
  private listeners = new Set<(event: TranslationEvent) => void>()
  private socket?: WebSocket
  private sessionId?: string
  private audioContext?: AudioContext
  private processor?: ScriptProcessorNode
  private sourceNode?: MediaStreamAudioSourceNode
  private started = 0
  async connect(session: TranslationSession) {
    this.started = Date.now()
    const base = (process.env.NEXT_PUBLIC_TRANSLATION_BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'https://hacknex-5sk1.onrender.com').trim()
    try {
      const response = await fetch(`${base.replace(/\/$/, '')}/api/sessions`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ source_language: session.sourceLanguage, target_language: session.targetLanguage }), signal: AbortSignal.timeout(5000) })
      if (!response.ok) throw new Error('backend-rejected')
      const created = await response.json() as { session_id: string; ws_token: string }
      this.sessionId = created.session_id
      const wsBase = base.replace(/^http/, 'ws').replace(/\/$/, '')
      this.socket = new WebSocket(`${wsBase}/ws/translate`)
      await new Promise<void>((resolve, reject) => { const socket = this.socket!; let settled = false; socket.onopen = () => { socket.send(JSON.stringify({ type: 'session.start', session_id: created.session_id, ws_token: created.ws_token, source_language: session.sourceLanguage, target_language: session.targetLanguage })) }; socket.onerror = () => { if (!settled) { settled = true; reject(new Error('backend-websocket')) } }; socket.onclose = () => { if (!settled) { settled = true; reject(new Error('backend-websocket')) } }; socket.onmessage = (event) => { const data = JSON.parse(String(event.data)) as Record<string, unknown>; this.handleMessage(String(event.data)); if (data.type === 'session.status' && data.state === 'connected' && !settled) { settled = true; resolve() } if (data.type === 'error' && !settled) { settled = true; reject(new Error(String(data.safe_message || 'Realtime backend rejected the session.'))) } } })
    } catch (cause) {
      const detail = cause instanceof DOMException && cause.name === 'TimeoutError' ? 'Realtime backend timed out.' : 'Realtime backend unavailable. Check the Render service URL and deployment.'
      this.emit({ type: 'error', message: detail, timestampMs: Date.now() })
      throw new Error(detail)
    }
  }
  sendAudio(audio: ArrayBuffer) { if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(audio) }
  async pause() { this.audioContext?.suspend() }
  async resume() { this.audioContext?.resume() }
  async end() { if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify({ type: 'session.end' })); this.socket?.close(); this.processor?.disconnect(); this.sourceNode?.disconnect(); await this.audioContext?.close() }
  onEvent(cb: (event: TranslationEvent) => void) { this.listeners.add(cb); return () => this.listeners.delete(cb) }
  attachMicrophone(stream: MediaStream) { const AudioContextClass = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext; if (!AudioContextClass) return; this.audioContext = new AudioContextClass({ sampleRate: 16000 }); this.sourceNode = this.audioContext.createMediaStreamSource(stream); this.processor = this.audioContext.createScriptProcessor(4096, 1, 1); this.processor.onaudioprocess = (event) => { const input = event.inputBuffer.getChannelData(0); const pcm = new ArrayBuffer(input.length * 2); const view = new DataView(pcm); input.forEach((value, index) => view.setInt16(index * 2, Math.max(-1, Math.min(1, value)) * 0x7fff, true)); this.sendAudio(pcm) }; this.sourceNode.connect(this.processor); const silentGain = this.audioContext.createGain(); silentGain.gain.value = 0; this.processor.connect(silentGain); silentGain.connect(this.audioContext.destination); void this.audioContext.resume() }
  private handleMessage(raw: string) { const data = JSON.parse(raw) as Record<string, unknown>; const timestampMs = typeof data.timestamp === 'number' ? data.timestamp * 1000 : Date.now(); if (data.type === 'transcript.partial') this.emit({ type: 'partial_source', text: String(data.text || ''), timestampMs }); else if (data.type === 'transcript.final') this.emit({ type: 'final_source', text: String(data.text || ''), timestampMs }); else if (data.type === 'translation.partial') this.emit({ type: 'partial_translation', text: String(data.translated_text || ''), timestampMs }); else if (data.type === 'translation.final') { this.emit({ type: 'final_translation', text: String(data.translated_text || ''), timestampMs }); this.emit({ type: 'metrics', timeToFirstWordMs: Date.now() - this.started, endOfSpeechToFinalMs: typeof data.end_to_end_latency_ms === 'number' ? data.end_to_end_latency_ms : undefined, timestampMs }) } else if (data.type === 'error') this.emit({ type: 'error', message: String(data.safe_message || 'Translation backend error.'), timestampMs }); else if (data.type === 'session.status' && data.state === 'connected') this.emit({ type: 'language_detected', language: 'Connected', timestampMs }) }
  protected emit(event: TranslationEvent) { this.listeners.forEach((listener) => listener(event)) }
}

export function createTranslationAdapter(): TranslationAdapter { return isMockEnabled() ? new MockAdapter() : new BackendAdapter() }

class MockAdapter extends BackendAdapter {
  private mockTimer?: ReturnType<typeof setTimeout>
  async connect(session: TranslationSession) { this.mockTimer = setTimeout(() => { const now = Date.now(); this.emitMock({ type: 'language_detected', language: session.sourceLanguage, timestampMs: now }); this.emitMock({ type: 'partial_source', text: 'வணக்கம், அனைவரும் எப்படி இருக்கிறீர்கள்?', timestampMs: now }); this.emitMock({ type: 'partial_translation', text: 'Hello, how is everyone?', timestampMs: now + 120 }); this.emitMock({ type: 'final_translation', text: 'Hello, how is everyone?', timestampMs: now + 620, confidence: 0.98 }); this.emitMock({ type: 'metrics', timeToFirstWordMs: 620, endOfSpeechToFinalMs: 620, timestampMs: now + 620 }) }, 900) }
  async pause() { if (this.mockTimer) clearTimeout(this.mockTimer) }
  async resume() {}
  async end() { if (this.mockTimer) clearTimeout(this.mockTimer) }
  private emitMock(event: TranslationEvent) { this.emit(event) }
}

export function isMockEnabled() { return process.env.NEXT_PUBLIC_USE_MOCK === 'true' }
export const supportedLanguages = ['Tamil', 'Hindi', 'English', 'Kannada', 'Telugu', 'Malayalam']
export const languageCodes: Record<string, string> = { Tamil: 'ta-IN', Hindi: 'hi-IN', English: 'en-IN', Kannada: 'kn-IN', Telugu: 'te-IN', Malayalam: 'ml-IN' }
export const languageNames: Record<string, string> = Object.fromEntries(Object.entries(languageCodes).map(([name, code]) => [code, name]))
export function formatMetric(value?: number) { return value == null ? 'Collecting' : `${Math.round(value)} ms` }
export function formatEventTime(ms: number) { return new Date(ms).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' }) }
export function audioFileIsWav(file: File) { return file.type === 'audio/wav' || file.type === 'audio/x-wav' || file.name.toLowerCase().endsWith('.wav') }
export function createRoomId() { return `HN-${crypto.randomUUID().slice(0, 8).toUpperCase()}` }
export function downloadFile(name: string, content: string, type: string) { const url = URL.createObjectURL(new Blob([content], { type })); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url) }
export function seconds(ms?: number) { return ms == null ? 'Not measured' : `${(ms / 1000).toFixed(2)}s` }
export function csvEscape(value: unknown) { return `"${String(value ?? 'Not measured').replaceAll('"', '""')}"` }
