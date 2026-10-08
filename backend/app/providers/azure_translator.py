import asyncio
import logging
from typing import Dict, Optional
import httpx

from app.config import settings
from app.errors import BhashaLiveException, ErrorCode
from app.languages import AZURE_TRANSLATOR_LANG_MAP
from app.providers.base import TranslationProvider

logger = logging.getLogger("bhashalive.provider.azure_translator")


class AzureTranslationProvider(TranslationProvider):
    """Fallback translation provider using Azure Cognitive Services Translator REST API v3.0."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout: float = 4.0,
    ):
        self.api_key = api_key or settings.azure_translator_key
        self.region = region or settings.azure_translator_region
        self.endpoint = endpoint or settings.azure_translator_endpoint
        self.timeout = timeout

    async def translate(
        self,
        text: str,
        src: str,
        tgt: str,
        glossary: Optional[Dict[str, str]] = None,
    ) -> str:
        if not text or not text.strip():
            return ""

        if not self.api_key or not self.api_key.strip():
            raise BhashaLiveException(
                code=ErrorCode.PROVIDER_NOT_CONFIGURED,
                safe_message="Azure Translator fallback provider is not configured.",
                retryable=False,
                detail="Missing AZURE_TRANSLATOR_KEY",
            )

        # Map language codes (e.g. ta-IN -> ta)
        azure_from = AZURE_TRANSLATOR_LANG_MAP.get(src, src.split("-")[0])
        azure_to = AZURE_TRANSLATOR_LANG_MAP.get(tgt, tgt.split("-")[0])

        url = f"{self.endpoint.rstrip('/')}/translate"
        params = {
            "api-version": "3.0",
            "from": azure_from,
            "to": azure_to,
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/json; charset=UTF-8",
        }
        if self.region:
            headers["Ocp-Apim-Subscription-Region"] = self.region

        payload = [{"Text": text.strip()}]

        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, params=params, json=payload, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        translations = data[0].get("translations", [])
                        if translations:
                            return translations[0].get("text", "").strip()
                    return ""

                if resp.status_code in (401, 403):
                    raise BhashaLiveException(
                        code=ErrorCode.PROVIDER_NOT_CONFIGURED,
                        safe_message="Azure Translator authentication failure.",
                        retryable=False,
                        detail=f"HTTP {resp.status_code}",
                    )

                if resp.status_code == 429:
                    raise BhashaLiveException(
                        code=ErrorCode.RATE_LIMIT_EXCEEDED,
                        safe_message="Azure Translator rate limit exceeded.",
                        retryable=True,
                    )

                logger.warning(f"Azure Translator HTTP {resp.status_code}: {resp.text}")

            except httpx.TimeoutException:
                if attempt == 2:
                    raise BhashaLiveException(
                        code=ErrorCode.TRANSLATION_FAILED,
                        safe_message="Azure Translator timed out.",
                        retryable=True,
                    )
            except BhashaLiveException:
                raise
            except Exception as e:
                logger.error(f"Azure Translator error: {e}")
                if attempt == 2:
                    raise BhashaLiveException(
                        code=ErrorCode.TRANSLATION_FAILED,
                        safe_message="Azure Translator request error.",
                        retryable=True,
                    )

            await asyncio.sleep(0.3)

        return ""
