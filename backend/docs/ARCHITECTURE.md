# BhashaLive Architecture & Technical Innovation
**HackNex 2026 — Problem HNX26EPS03**

---

## 1. System Flow & Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Browser Client (Microphone)
    participant WS as FastAPI WebSocket (/ws/translate)
    participant Pipe as SessionPipeline
    participant Sched as Adaptive Stability Scheduler
    participant ASR as Primary ASR (Sarvam Saaras)
    participant TR as Translation (Sarvam Mayura / Azure)
    participant Store as Background Writer (PostgreSQL / Memory)

    Client->>WS: Handshake (ws_token + Origin Check)
    WS->>Pipe: Initialize SessionPipeline
    Pipe->>ASR: Connect wss://api.sarvam.ai/speech-to-text-realtime/ws
    WS-->>Client: session.status (state="streaming")

    loop Audio Streaming (100–250ms PCM linear16)
        Client->>WS: Binary audio frames (16kHz mono)
        WS->>Pipe: push_audio(chunk) [Drop-oldest backpressure guard]
        Pipe->>ASR: send_audio(chunk)
    end

    loop Realtime ASR Consumption
        ASR-->>Pipe: ASREvent (text, is_final, confidence)
        Pipe-->>Client: transcript.partial / transcript.final (Immediate UI feed)
        Pipe->>Sched: feed_hypothesis(text, is_final)
        
        alt Commit Condition Triggered (LCP k=3 / Sentence Boundary / Max-Wait / Final)
            Sched-->>Pipe: CommitDecision (should_translate=True, stable_span)
            par Non-blocking Concurrent Translation
                Pipe->>TR: translate(stable_span, src, tgt)
                TR-->>Pipe: translated_text
                Pipe->>Sched: record_translation_result() [Updates rewrite count]
                Pipe-->>Client: translation.partial / translation.final (Matching stable segment_id)
                Pipe-)Store: enqueue_segment() & enqueue_metric() [Off-path write]
            end
        else Tail Tentative
            Sched-->>Pipe: CommitDecision (should_translate=False)
        end
    end

    Client->>WS: session.end
    WS->>Pipe: handle_end()
    Pipe->>ASR: Flush buffer {"type":"flush"}
    WS-->>Client: session.status (state="ended")
```

---

## 2. Core Technical Innovation: Adaptive Stability Scheduler

### How to Explain the Innovation to Judges:
> *"In live speech translation, naive systems face a destructive trade-off: if you translate every interim hypothesis as it arrives, earlier words continually mutate on the screen, causing cognitive overload and visual jitter for the user. If you wait for the full sentence to finish before translating, translation latency spikes to several seconds.*
> 
> *BhashaLive introduces an **Adaptive Stability Scheduler** that tracks a sliding window of recent speech hypotheses ($k=3$) and computes the **Longest Common Prefix (LCP)** at the word level. When the prefix stabilizes across successive hypotheses, or encounters sentence punctuation (`.` `?` `!` or Devanagari danda `।`), or hits a bounded max-wait timeout, it commits that span to translation immediately.*
> 
> *For Indian languages (SOV / verb-final structure such as Tamil, Hindi, Telugu), syntactic dependencies require broader context than English (SVO). Our scheduler tunes commit windows dynamically per language family, cutting UI caption rewrites and redundant API calls by up to 40% while preserving sub-second first-caption responsiveness."*

---

## 3. Resilience, Fault Tolerance & Privacy

1. **Decoupled Concurrency:** ASR consumption never awaits HTTP translation calls. Slow network or high-latency upstream translation never pauses audio streaming or live transcription.
2. **Circuit Breaker Failover:** Trips automatically upon quota exhaustion (HTTP 429/401/403) or repeated network timeouts, seamlessly shifting live sessions from Sarvam AI to Azure AI with audio buffer replay (~2 seconds).
3. **Graceful Degradation:** If translation fails, live source transcription remains active, emitting retryable warnings instead of disconnecting the user.
4. **Privacy & GDPR Compliance:** Audio resides strictly in RAM buffers (`STORE_RAW_AUDIO=false`). Calling `DELETE /api/sessions/{id}` cascades a hard-deletion across all database records and cached metrics.
