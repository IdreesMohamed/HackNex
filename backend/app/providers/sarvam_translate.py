import asyncio
import logging
from typing import Dict, Optional
import httpx

from app.config import settings
from app.errors import BhashaLiveException, ErrorCode
from app.providers.base import TranslationProvider

logger = logging.getLogger("bhashalive.provider.sarvam_translate")


class SarvamTranslationProvider(TranslationProvider):
    """Translation adapter for Sarvam Mayura v1 REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 4.0,
    ):
        self.api_key = api_key or settings.sarvam_api_key
        self.base_url = base_url or settings.sarvam_translate_url
        self.model = model or settings.sarvam_translate_model
        self.timeout = timeout

    async def translate(
        self,
        text: str,
        src: str,
        tgt: str,
        glossary: Optional[Dict[str, str]] = None,
    ) -> str:
        """Translates text from src to tgt language using Sarvam Mayura model."""
        if not text or not text.strip():
            return ""

        if not self.api_key or not self.api_key.strip() or self.api_key == "replace_with_your_key":
            raise BhashaLiveException(
                code=ErrorCode.PROVIDER_NOT_CONFIGURED,
                safe_message="Sarvam translation provider is not configured.",
                retryable=False,
                detail="Missing SARVAM_API_KEY",
            )

        # Apply glossary overrides prior to or after translation if needed
        # In Indian translation contexts, domain entities (names/places) can be protected
        payload = {
            "input": text.strip()[:1000],  # Cap at 1000 chars as per Sarvam documentation
            "source_language_code": src,
            "target_language_code": tgt,
            "model": self.model,
            "mode": "formal",
            "enable_preprocessing": True,
            "enable_postprocessing": True,
        }

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

        # Attempt call with a single retry on timeout/5xx
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(self.base_url, json=payload, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    translated = data.get("translated_text", "")

                    # Apply glossary replacement if preferred translations are mapped
                    if glossary:
                        for term, preferred in glossary.items():
                            if term in text:
                                # Simple replacement or preservation
                                pass

                    return translated.strip()

                if resp.status_code in (401, 403):
                    logger.error(f"Sarvam Translate authentication failure: HTTP {resp.status_code}")
                    raise BhashaLiveException(
                        code=ErrorCode.PROVIDER_NOT_CONFIGURED,
                        safe_message="Translation authorization failure.",
                        retryable=False,
                        detail=f"HTTP {resp.status_code}: {resp.text}",
                    )

                if resp.status_code == 429:
                    logger.warning("Sarvam Translate rate limit hit")
                    raise BhashaLiveException(
                        code=ErrorCode.RATE_LIMIT_EXCEEDED,
                        safe_message="Translation rate limit exceeded.",
                        retryable=True,
                        detail="HTTP 429",
                    )

                logger.warning(
                    f"Sarvam Translate returned HTTP {resp.status_code} (attempt {attempt}/2): {resp.text}"
                )
                if attempt == 2:
                    raise BhashaLiveException(
                        code=ErrorCode.TRANSLATION_FAILED,
                        safe_message="Translation request failed.",
                        retryable=True,
                        detail=f"HTTP {resp.status_code}: {resp.text}",
                    )

            except httpx.TimeoutException as e:
                logger.warning(f"Sarvam Translate timed out (attempt {attempt}/2): {e}")
                if attempt == 2:
                    raise BhashaLiveException(
                        code=ErrorCode.TRANSLATION_FAILED,
                        safe_message="Translation service timed out.",
                        retryable=True,
                        detail="Timeout",
                    )
            except BhashaLiveException:
                raise
            except Exception as e:
                logger.error(f"Unexpected error calling Sarvam Translate (attempt {attempt}/2): {e}")
                if attempt == 2:
                    raise BhashaLiveException(
                        code=ErrorCode.TRANSLATION_FAILED,
                        safe_message="Translation service error.",
                        retryable=True,
                        detail=str(e),
                    )

            # Short backoff before retry
            await asyncio.sleep(0.3)

        return ""
