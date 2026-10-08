from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# --- Health & Diagnostics ---
class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "bhashalive-backend"
    version: str = "0.1.0"


class ProviderHealthItem(BaseModel):
    configured: bool
    reachable: bool
    latency_ms: Optional[float] = None


class ProvidersHealthResponse(BaseModel):
    sarvam_asr: ProviderHealthItem
    sarvam_translate: ProviderHealthItem
    sarvam_tts: ProviderHealthItem
    azure_speech: ProviderHealthItem
    azure_translator: ProviderHealthItem


# --- Languages ---
class LanguageItem(BaseModel):
    code: str
    name: str
    native_name: str
    validated: bool
    is_verb_final: bool


class LanguagesResponse(BaseModel):
    languages: List[LanguageItem]


# --- Sessions ---
class CreateSessionRequest(BaseModel):
    source_language: str = Field(..., examples=["ta-IN"])
    target_language: str = Field(..., examples=["en-IN"])


class SessionResponse(BaseModel):
    session_id: str
    ws_token: str
    source_language: str
    target_language: str
    status: str
    expires_at: str


class SegmentResponse(BaseModel):
    segment_id: str
    sequence_no: int
    source_text: str
    translated_text: str
    confidence: float
    stability_score: float
    rewrite_count: int
    created_at: str


class SessionMetricsResponse(BaseModel):
    session_id: str
    first_caption_latency_ms: Optional[float] = None
    final_latency_ms: Optional[float] = None
    rewrite_count: int = 0
    translation_call_count: int = 0


# --- Translation ---
class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    source_language: str = Field(..., examples=["ta-IN"])
    target_language: str = Field(..., examples=["en-IN"])


class TranslateResponse(BaseModel):
    translated_text: str
    source_language: str
    target_language: str
    provider: str
    latency_ms: float


# --- Glossary ---
class GlossaryTermCreate(BaseModel):
    term: str = Field(..., min_length=1)
    source_language: str
    target_language: str
    preferred_translation: str


class GlossaryTermResponse(BaseModel):
    id: str
    term: str
    source_language: str
    target_language: str
    preferred_translation: str


# --- WebSocket Messages (Client -> Server) ---
class WSSessionStart(BaseModel):
    type: Literal["session.start"] = "session.start"
    session_id: Optional[str] = None
    source_language: str
    target_language: str
    ws_token: Optional[str] = None


class WSSessionEnd(BaseModel):
    type: Literal["session.end"] = "session.end"


class WSPing(BaseModel):
    type: Literal["ping"] = "ping"


# --- WebSocket Messages (Server -> Client) ---
class WSSessionStatus(BaseModel):
    type: Literal["session.status"] = "session.status"
    state: Literal["connected", "streaming", "degraded", "ended"]
    latency_ms: Optional[float] = None
    provider: str
    session_id: str


class WSTranscriptPartial(BaseModel):
    type: Literal["transcript.partial"] = "transcript.partial"
    segment_id: str
    text: str
    timestamp: float
    confidence: float = 1.0
    stability_score: float = 0.0


class WSTranscriptFinal(BaseModel):
    type: Literal["transcript.final"] = "transcript.final"
    segment_id: str
    text: str
    timestamp: float


class WSTranslationPartial(BaseModel):
    type: Literal["translation.partial"] = "translation.partial"
    segment_id: str
    translated_text: str
    source_text: str


class WSTranslationFinal(BaseModel):
    type: Literal["translation.final"] = "translation.final"
    segment_id: str
    translated_text: str
    source_text: str
    translation_latency_ms: float
    end_to_end_latency_ms: float
    audio_base64: Optional[str] = None


class WSError(BaseModel):
    type: Literal["error"] = "error"
    code: str
    safe_message: str
    retryable: bool = False


class WSPong(BaseModel):
    type: Literal["pong"] = "pong"
