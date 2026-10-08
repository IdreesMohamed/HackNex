import asyncio
import logging
import time
from collections import deque
from enum import Enum
from typing import AsyncIterator, Callable, Dict, Optional

from app.config import settings
from app.errors import BhashaLiveException, ErrorCode
from app.providers.azure_speech import AzureSpeechASRProvider
from app.providers.azure_translator import AzureTranslationProvider
from app.providers.base import ASREvent, ASRProvider, TranslationProvider
from app.providers.sarvam_asr import SarvamASRProvider
from app.providers.sarvam_translate import SarvamTranslationProvider

logger = logging.getLogger("bhashalive.provider.router")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal operation: traffic routes to primary
    OPEN = "OPEN"            # Tripped: traffic routes directly to fallback
    HALF_OPEN = "HALF_OPEN"  # Testing: allow single probe to primary


class CircuitBreaker:
    """Standard Circuit Breaker pattern with consecutive failure threshold and recovery timeout."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        clock_func: Optional[Callable[[], float]] = None,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.clock = clock_func or time.time

        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0.0

    def can_attempt(self) -> bool:
        """Determines if a request to the primary provider is allowed."""
        now = self.clock()
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if (now - self.last_failure_time) >= self.recovery_timeout:
                logger.info("Circuit breaker transitioning from OPEN to HALF_OPEN probe")
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self) -> None:
        """Records a successful call, resetting failure counts."""
        if self.state != CircuitState.CLOSED:
            logger.info("Circuit breaker probe succeeded; transitioning to CLOSED")
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0

    def record_failure(self, force_open: bool = False) -> None:
        """Records a failure. If threshold met or force_open=True, trips to OPEN."""
        self.consecutive_failures += 1
        self.last_failure_time = self.clock()
        if force_open or self.consecutive_failures >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker tripped to OPEN (consecutive failures={self.consecutive_failures})"
            )
            self.state = CircuitState.OPEN


class RoutedTranslationProvider(TranslationProvider):
    """Translation provider that routes between Sarvam (primary) and Azure (fallback)

    via a Circuit Breaker.
    """

    def __init__(
        self,
        primary: Optional[TranslationProvider] = None,
        fallback: Optional[TranslationProvider] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.primary = primary or SarvamTranslationProvider()
        self.fallback = fallback or AzureTranslationProvider()
        self.breaker = circuit_breaker or CircuitBreaker()
        self.active_provider_name = "sarvam"

    async def translate(
        self,
        text: str,
        src: str,
        tgt: str,
        glossary: Optional[Dict[str, str]] = None,
    ) -> str:
        # Check if primary can be attempted
        if settings.enable_fallback and not self.breaker.can_attempt():
            logger.info("Circuit OPEN: routing translation directly to Azure fallback")
            self.active_provider_name = "azure"
            return await self.fallback.translate(text, src, tgt, glossary)

        # Attempt primary
        try:
            self.active_provider_name = "sarvam"
            result = await self.primary.translate(text, src, tgt, glossary)
            self.breaker.record_success()
            return result
        except BhashaLiveException as e:
            # Check if failover needed
            is_quota_or_auth = e.code in (ErrorCode.RATE_LIMIT_EXCEEDED, ErrorCode.PROVIDER_NOT_CONFIGURED)
            self.breaker.record_failure(force_open=is_quota_or_auth)

            if settings.enable_fallback and (settings.is_azure_translator_configured or self.fallback):
                logger.warning(f"Primary translation failed ({e.code}); falling back to Azure")
                self.active_provider_name = "azure"
                return await self.fallback.translate(text, src, tgt, glossary)
            raise
        except Exception as e:
            self.breaker.record_failure()
            if settings.enable_fallback and (settings.is_azure_translator_configured or self.fallback):
                logger.warning(f"Unexpected primary failure ({e}); falling back to Azure")
                self.active_provider_name = "azure"
                return await self.fallback.translate(text, src, tgt, glossary)
            raise


class RoutedASRProvider(ASRProvider):
    """Streaming ASR provider that manages Sarvam primary and Azure fallback with buffer replay."""

    def __init__(
        self,
        primary: Optional[ASRProvider] = None,
        fallback: Optional[ASRProvider] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        buffer_size: int = 20,  # ~2 seconds buffer
    ):
        self.primary = primary or SarvamASRProvider()
        self.fallback = fallback or AzureSpeechASRProvider()
        self.breaker = circuit_breaker or CircuitBreaker()
        self.buffer: deque[bytes] = deque(maxlen=buffer_size)

        self.current_provider: ASRProvider = self.primary
        self.active_provider_name = "sarvam"
        self._language: Optional[str] = None
        self._is_failing_over = False

    @property
    def is_connected(self) -> bool:
        return self.current_provider.is_connected

    async def start(self, language: str) -> None:
        self._language = language
        try:
            await self.primary.start(language)
            self.current_provider = self.primary
            self.active_provider_name = "sarvam"
            self.breaker.record_success()
        except Exception as e:
            logger.warning(f"Failed to start primary Sarvam ASR: {e}")
            self.breaker.record_failure(force_open=True)
            if settings.enable_fallback and (settings.is_azure_speech_configured or self.fallback):
                logger.info("Failing over ASR to Azure Speech")
                await self.fallback.start(language)
                self.current_provider = self.fallback
                self.active_provider_name = "azure"
            else:
                raise

    async def send_audio(self, chunk: bytes) -> None:
        self.buffer.append(chunk)
        try:
            await self.current_provider.send_audio(chunk)
        except Exception as e:
            logger.error(f"Error sending audio to {self.active_provider_name} ASR: {e}")
            if self.current_provider == self.primary and settings.enable_fallback:
                await self._trigger_asr_failover()
                await self.current_provider.send_audio(chunk)
            else:
                raise

    async def _trigger_asr_failover(self) -> None:
        """Switches active provider to fallback and replays recently buffered chunks."""
        if self._is_failing_over:
            return
        self._is_failing_over = True
        logger.warning("Triggering ASR failover from Sarvam to Azure with audio buffer replay")
        self.breaker.record_failure(force_open=True)
        try:
            await self.fallback.start(self._language or "en-IN")
            self.current_provider = self.fallback
            self.active_provider_name = "azure"
            # Replay buffered chunks (~2s)
            for chunk in list(self.buffer):
                await self.fallback.send_audio(chunk)
            logger.info(f"Replayed {len(self.buffer)} audio chunks to fallback ASR")
        finally:
            self._is_failing_over = False

    async def events(self) -> AsyncIterator[ASREvent]:
        async for event in self.current_provider.events():
            yield event

    async def flush(self) -> None:
        await self.current_provider.flush()

    async def close(self) -> None:
        await self.primary.close()
        await self.fallback.close()
