import base64
import logging
from typing import Optional
import httpx

from app.config import settings
from app.errors import BhashaLiveException, ErrorCode
from app.providers.base import TTSProvider

logger = logging.getLogger("bhashalive.provider.sarvam_tts")


class SarvamTTSProvider(TTSProvider):
    """Text-to-speech provider using Sarvam Bulbul v3 model."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        speaker: str = "aditya",
    ):
        self.api_key = api_key or settings.sarvam_api_key
        self.base_url = base_url or settings.sarvam_tts_url
        self.speaker = speaker

    async def synthesize(self, text: str, lang: str) -> bytes:
        """Synthesizes text into WAV audio bytes using Sarvam Bulbul."""
        if not settings.enable_tts:
            raise BhashaLiveException(
                code=ErrorCode.INTERNAL_ERROR,
                safe_message="Text-to-speech feature is disabled.",
                retryable=False,
            )

        if not self.api_key or not self.api_key.strip():
            raise BhashaLiveException(
                code=ErrorCode.PROVIDER_NOT_CONFIGURED,
                safe_message="TTS provider is not configured.",
                retryable=False,
            )

        payload = {
            "inputs": [text.strip()[:2500]],
            "target_language_code": lang,
            "speaker": self.speaker,
            "pace": 1.0,
            "speech_sample_rate": 16000,
            "model": "bulbul:v3",
        }
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(self.base_url, json=payload, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            audios = data.get("audios", [])
            if audios and len(audios) > 0:
                # Sarvam returns base64-encoded WAV
                return base64.b64decode(audios[0])
            raise BhashaLiveException(
                code=ErrorCode.INTERNAL_ERROR,
                safe_message="No audio returned from TTS service.",
                retryable=True,
            )

        raise BhashaLiveException(
            code=ErrorCode.INTERNAL_ERROR,
            safe_message="Failed to synthesize speech.",
            retryable=True,
            detail=f"HTTP {resp.status_code}: {resp.text}",
        )
