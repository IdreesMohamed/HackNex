export type ConnectionState = 'idle' | 'connecting' | 'listening' | 'degraded' | 'ended' | 'error'

export type CaptionSegment = {
  id: string
  source: string
  translation: string
  isPartial?: boolean
  confidence?: number
  timestamp: string
}

export type TranslationSession = {
  sourceLanguage: string
  targetLanguage: string
  state: ConnectionState
  provider: string
  latencyMs: number
  segments: CaptionSegment[]
}

export interface TranslationConnector {
  connect(session: Pick<TranslationSession, 'sourceLanguage' | 'targetLanguage'>): Promise<void>
  pause(): Promise<void>
  resume(): Promise<void>
  end(): Promise<void>
  onCaption(callback: (segment: CaptionSegment) => void): () => void
  onStateChange(callback: (state: ConnectionState) => void): () => void
}

export class DemoTranslationConnector implements TranslationConnector {
  private captionListeners = new Set<(segment: CaptionSegment) => void>()
  private stateListeners = new Set<(state: ConnectionState) => void>()
  private timer?: ReturnType<typeof setTimeout>
  private stopped = false

  async connect(session: Pick<TranslationSession, 'sourceLanguage' | 'targetLanguage'>) {
    this.stopped = false
    this.emitState('connecting')
    await new Promise((resolve) => setTimeout(resolve, 650))
    if (!this.stopped) this.emitState('listening')
    this.timer = setTimeout(() => {
      if (!this.stopped) {
        this.emitCaption({ id: 'demo-1', source: 'வணக்கம், அனைவரும் எப்படி இருக்கிறீர்கள்?', translation: 'Hello, how is everyone?', timestamp: '00:04', confidence: 0.98 })
      }
    }, 1200)
  }

  async pause() { this.emitState('idle') }
  async resume() { this.emitState('listening') }
  async end() { this.stopped = true; if (this.timer) clearTimeout(this.timer); this.emitState('ended') }
  onCaption(callback: (segment: CaptionSegment) => void) { this.captionListeners.add(callback); return () => this.captionListeners.delete(callback) }
  onStateChange(callback: (state: ConnectionState) => void) { this.stateListeners.add(callback); return () => this.stateListeners.delete(callback) }
  private emitCaption(segment: CaptionSegment) { this.captionListeners.forEach((listener) => listener(segment)) }
  private emitState(state: ConnectionState) { this.stateListeners.forEach((listener) => listener(state)) }
}
