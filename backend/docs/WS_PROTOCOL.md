# BhashaLive WebSocket Protocol Specification (`/ws/translate`)

## 1. Connection & Handshake
* **Endpoint:** `ws://<host>:<port>/ws/translate` (or `wss://` in production)
* **Query Parameters (Optional):**
  * `token`: Signed HMAC-SHA256 session token from `POST /api/sessions`.
  * `session_id`: UUID session identifier.
* **Origin Validation:** The `Origin` header must match configured `ALLOWED_WS_ORIGINS` (e.g. `http://localhost:5173,http://localhost:3000`).

---

## 2. Audio Format Specification
* **Codec:** Linear PCM (signed 16-bit little-endian, `s16le`).
* **Sample Rate:** 16,000 Hz (16 kHz).
* **Channels:** 1 (mono).
* **Chunk Sizing:** Recommended 100 ms to 250 ms (3,200 to 8,000 bytes per binary frame).
* **Limit:** Enforced `MAX_AUDIO_CHUNK_BYTES = 65536`.

---

## 3. Client -> Server Messages

### 3.1 Session Start (`session.start`)
Must be the first message sent immediately upon connection:
```json
{
  "type": "session.start",
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "source_language": "ta-IN",
  "target_language": "en-IN",
  "ws_token": "eyJzIjoiM2ZhODVmNjQtNTcxNy00NTYyLWIzZmMtMmM5NjNmNjZhZmE2IiwiZSI6MTcyODQ..."
}
```

### 3.2 Binary Audio Frames
The browser sends raw 16 kHz mono 16-bit PCM binary frames to BhashaLive. BhashaLive encodes each PCM chunk as a base64 JSON `audio_input` event when sending it to Sarvam's realtime ASR WebSocket.

### 3.3 Session End (`session.end`)
Notifies server that the speaker has finished and requests buffer flush:
```json
{
  "type": "session.end"
}
```

### 3.4 Ping (`ping`)
```json
{
  "type": "ping"
}
```

---

## 4. Server -> Client Messages

### 4.1 Session Status (`session.status`)
```json
{
  "type": "session.status",
  "state": "streaming",
  "provider": "sarvam",
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```
*Possible states:* `connected`, `streaming`, `degraded`, `ended`.

### 4.2 Partial Transcript (`transcript.partial`)
Emitted as words are recognized by the upstream ASR engine:
```json
{
  "type": "transcript.partial",
  "segment_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "நான் நாளைக்கு",
  "timestamp": 1728400000.12,
  "confidence": 0.94,
  "stability_score": 0.67
}
```
*(UI displays tentative tail in gray).*

### 4.3 Final Transcript (`transcript.final`)
Emitted when an utterance finishes:
```json
{
  "type": "transcript.final",
  "segment_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "நான் நாளைக்கு சென்னைக்கு போகிறேன்.",
  "timestamp": 1728400001.55
}
```

### 4.4 Partial Translation (`translation.partial`)
Emitted when the Adaptive Stability Scheduler commits a stable prefix span:
```json
{
  "type": "translation.partial",
  "segment_id": "550e8400-e29b-41d4-a716-446655440000",
  "translated_text": "I will go tomorrow",
  "source_text": "நான் நாளைக்கு"
}
```

### 4.5 Final Translation (`translation.final`)
Emitted when the final translation is produced:
```json
{
  "type": "translation.final",
  "segment_id": "550e8400-e29b-41d4-a716-446655440000",
  "translated_text": "I am going to Chennai tomorrow.",
  "source_text": "நான் நாளைக்கு சென்னைக்கு போகிறேன்.",
  "translation_latency_ms": 320.4,
  "end_to_end_latency_ms": 1150.2
}
```

### 4.6 Error Event (`error`)
```json
{
  "type": "error",
  "code": "TRANSLATION_FAILED",
  "safe_message": "Translation service degraded; showing transcript.",
  "retryable": true
}
```

### 4.7 Pong (`pong`)
```json
{
  "type": "pong"
}
```

---

## 5. Segment ID Guarantee
A **`segment_id` is stable for the lifetime of one utterance**. All `transcript.partial`, `transcript.final`, `translation.partial`, and `translation.final` messages for that utterance share the identical `segment_id`. The client UI replaces captions by `segment_id` rather than blindly appending, eliminating visual duplicates.
