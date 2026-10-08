import asyncio
import logging
from typing import AsyncIterator, List, Optional
from collections import deque

from app.config import settings
from app.errors import BhashaLiveException, ErrorCode
from app.languages import AZURE_SPEECH_LANG_MAP
from app.providers.base import ASREvent, ASRProvider

logger = logging.getLogger("bhashalive.provider.azure_speech")


class AzureSpeechASRProvider(ASRProvider):
    """Fallback streaming ASR provider using Azure AI Speech Services."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.api_key = api_key or settings.azure_speech_key
        self.region = region or settings.azure_speech_region
        self.language: Optional[str] = None
        self._connected = False
        self._closed = False
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._event_queue: asyncio.Queue[ASREvent] = asyncio.Queue()

    @property
    def is_connected(self) -> bool:
        return self._connected and not self._closed

    async def start(self, language: str) -> None:
        if not self.api_key or not self.region:
            raise BhashaLiveException(
                code=ErrorCode.PROVIDER_NOT_CONFIGURED,
                safe_message="Azure Speech fallback provider is not configured.",
                retryable=False,
                detail="Missing AZURE_SPEECH_KEY or AZURE_SPEECH_REGION",
            )
        self.language = language
        self._connected = True
        self._closed = False
        logger.info(f"Started Azure Speech fallback ASR for language: {language}")

    async def send_audio(self, chunk: bytes) -> None:
        if not self.is_connected:
            return
        await self._audio_queue.put(chunk)

    async def events(self) -> AsyncIterator[ASREvent]:
        while not self._closed:
            try:
                # Wait for queued events or simulated responses
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def push_mock_event(self, event: ASREvent) -> None:
        """Helper to inject recognized events during fallback simulation/testing."""
        await self._event_queue.put(event)

    async def flush(self) -> None:
        logger.debug("Flushed Azure Speech ASR")

    async def close(self) -> None:
        self._closed = True
        self._connected = False
        logger.debug("Closed Azure Speech ASR")
