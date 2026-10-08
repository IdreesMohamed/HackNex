import base64
import logging
import time
from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from app.config import settings
from app.errors import BhashaLiveException, ErrorCode
from app.languages import is_language_supported
from app.providers.sarvam_tts import SarvamTTSProvider

logger = logging.getLogger("bhashalive.api.tts")
router = APIRouter(tags=["TTS"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    target_language: str = Field(..., examples=["en-IN", "ta-IN", "hi-IN"])
    speaker: str = Field(default="aditya")


class TTSResponse(BaseModel):
    audio_base64: str
    format: str = "audio/wav"
    latency_ms: float


@router.post("/tts", response_model=TTSResponse)
async def synthesize_speech(req: TTSRequest) -> TTSResponse:
    """Synthesizes text into speech and returns base64-encoded WAV audio."""
    if not settings.enable_tts:
        raise BhashaLiveException(
            code=ErrorCode.INTERNAL_ERROR,
            safe_message="Text-to-speech feature is disabled.",
            retryable=False,
        )

    t0 = time.perf_counter()
    provider = SarvamTTSProvider(speaker=req.speaker)
    audio_bytes = await provider.synthesize(text=req.text, lang=req.target_language)
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    b64 = base64.b64encode(audio_bytes).decode("utf-8")

    return TTSResponse(
        audio_base64=b64,
        format="audio/wav",
        latency_ms=latency_ms,
    )


@router.post("/tts/raw")
async def synthesize_speech_raw(req: TTSRequest):
    """Synthesizes text into speech and returns direct binary audio/wav stream."""
    if not settings.enable_tts:
        raise BhashaLiveException(
            code=ErrorCode.INTERNAL_ERROR,
            safe_message="Text-to-speech feature is disabled.",
            retryable=False,
        )

    provider = SarvamTTSProvider(speaker=req.speaker)
    audio_bytes = await provider.synthesize(text=req.text, lang=req.target_language)
    return Response(content=audio_bytes, media_type="audio/wav")
