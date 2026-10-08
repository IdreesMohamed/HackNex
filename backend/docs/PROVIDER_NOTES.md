# Provider Notes & Contract Verification
**BhashaLive Backend — HackNex 2026 (HNX26EPS03)**

This document details the live API contracts, endpoints, query parameters, auth mechanisms, audio formats, payloads, and assumptions verified from official documentation.

---

## 1. Sarvam AI: Realtime Streaming Speech-to-Text (Primary ASR)

* **Documentation Sources:**
  - Official Portal: [https://docs.sarvam.ai](https://docs.sarvam.ai)
  - WebSocket Guide: `https://docs.sarvam.ai/speech-to-text-realtime/ws`
  - GitHub Cookbook: [https://github.com/sarvam-ai/cookbook](https://github.com/sarvam-ai/cookbook)
* **WebSocket Endpoint URL:**
  `wss://api.sarvam.ai/speech-to-text-realtime/ws`
* **Authentication:**
  - Request Header: `api-subscription-key: <SARVAM_API_KEY>` (in WebSocket handshake)
* **Connection Query Parameters:**
  - `language_code`: BCP-47 language tag (`ta-IN`, `hi-IN`, `en-IN`, `te-IN`, `kn-IN`, `ml-IN`, or `auto`)
  - `model`: `saaras:v3-realtime` (default) or `saaras:v4`
  - `stream_type`: `balanced` (optimizes latency vs accuracy)
  - `mode`: `transcribe`
  - `endpointing`: `vad` (server-side millisecond VAD)
  - `encoding`: `linear16` (signed 16-bit little-endian PCM)
  - `sample_rate`: `16000` (16 kHz mono)
* **Client -> Upstream Audio Frames:**
  - Raw binary frames containing linear16 PCM audio.
  - Recommended chunk size: 100 ms – 250 ms (3,200 to 8,000 bytes at 16kHz 16-bit mono).
* **Finalization / Flush:**
  - Client sends JSON text frame: `{"type": "flush"}` to flush pending audio buffers and obtain the final transcription.
* **Upstream -> Client Messages:**
  - Interim & final transcripts:
    ```json
    {
      "type": "transcript",
      "text": "வணக்கம்",
      "language_code": "ta-IN",
      "is_final": false,
      "confidence": 0.95
    }
    ```
  - VAD events: `{"type": "events", "name": "START_SPEECH"}` / `{"type": "events", "name": "END_SPEECH"}`
  - Error frames: `{"type": "error", "message": "...", "code": 401}`
* **Assumptions & Resilience:**
  - If upstream WebSocket connection drops, the client maintains a ring buffer of recent audio chunks (~2 seconds) and attempts exponential backoff reconnects up to 3 times.
  - If reconnect fails or quota error (401/429) occurs, the circuit breaker opens and fails over to Azure Speech.

---

## 2. Sarvam AI: Mayura Translate (Primary Translation)

* **Documentation Sources:**
  - REST Reference: `https://docs.sarvam.ai/api-reference/translate`
* **HTTP Endpoint:**
  - `POST https://api.sarvam.ai/translate`
* **Authentication:**
  - Header: `api-subscription-key: <SARVAM_API_KEY>`
  - Header: `Content-Type: application/json`
* **Request Schema:**
  ```json
  {
    "input": "நான் நாளைக்கு சென்னைக்கு போகிறேன்.",
    "source_language_code": "ta-IN",
    "target_language_code": "en-IN",
    "model": "mayura:v1",
    "mode": "formal",
    "enable_preprocessing": true,
    "enable_postprocessing": true
  }
  ```
* **Response Schema:**
  ```json
  {
    "request_id": "20261008_abc123xyz",
    "translated_text": "I am going to Chennai tomorrow.",
    "source_language_code": "ta-IN"
  }
  ```
* **Limits & Constraints:**
  - Input text must not exceed 1,000 characters per call.
  - Rate limits must be managed via client-side debouncing and caching.

---

## 3. Sarvam AI: Bulbul TTS (Optional Feature-Flagged)

* **Documentation Sources:**
  - REST Reference: `https://docs.sarvam.ai/api-reference/text-to-speech`
* **HTTP Endpoint:**
  - `POST https://api.sarvam.ai/text-to-speech`
* **Authentication:**
  - Header: `api-subscription-key: <SARVAM_API_KEY>`
  - Header: `Content-Type: application/json`
* **Request Schema:**
  ```json
  {
    "text": "வணக்கம், நீங்கள் நலமா?",
    "language_code": "ta-IN",
    "speaker": "shubh",
    "pace": 1.0,
    "temperature": 0.6
  }
  ```
* **Response Schema:**
  ```json
  {
    "request_id": "20261008_tts987",
    "audios": [
      "UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA="
    ]
  }
  ```
* **Audio Format:** Base64-encoded WAV format.

---

## 4. Azure AI Speech (Fallback Streaming Speech Translation)

* **Documentation Sources:**
  - Microsoft Learn: [Azure Speech SDK Speech Translation](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-translation)
* **SDK / Transport:**
  - Python SDK `azure.cognitiveservices.speech` or HTTP/WebSocket fallback adapter.
  - Utilizes `TranslationRecognizer` connected to `PushAudioInputStream(AudioStreamFormat(16000, 16, 1))`.
* **Credentials:**
  - `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`
* **Events Emitted:**
  - `recognizing`: Interim translation & transcription.
  - `recognized`: Final translation & transcription.
* **Failover Logic:**
  - When Sarvam ASR fails or circuit breaker trips, the pipeline instantiates the Azure Speech recognizer and feeds the audio stream seamlessly.

---

## 5. Azure AI Translator (Fallback Text Translation)

* **Documentation Sources:**
  - Microsoft Learn: [Azure Translator REST API v3.0](https://learn.microsoft.com/en-us/azure/ai-services/translator/reference/v3-0-translate)
* **HTTP Endpoint:**
  - `POST https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to={target}&from={source}`
* **Authentication:**
  - Header: `Ocp-Apim-Subscription-Key: <AZURE_TRANSLATOR_KEY>`
  - Header: `Ocp-Apim-Subscription-Region: <AZURE_TRANSLATOR_REGION>`
  - Header: `Content-Type: application/json; charset=UTF-8`
* **Request Payload:**
  ```json
  [
    {"Text": "நான் நாளைக்கு சென்னைக்கு போகிறேன்."}
  ]
  ```
* **Response Payload:**
  ```json
  [
    {
      "detectedLanguage": {"language": "ta", "score": 1.0},
      "translations": [
        {"text": "I am going to Chennai tomorrow.", "to": "en"}
      ]
    }
  ]
  ```
* **Language Codes:** Maps `en-IN -> en`, `ta-IN -> ta`, `hi-IN -> hi`, `te-IN -> te`, `kn-IN -> kn`, `ml-IN -> ml`.
