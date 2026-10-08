from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Optional
from pydantic import BaseModel, Field


class ASREvent(BaseModel):
    """Normalized speech recognition event from any upstream ASR provider."""

    text: str
    is_final: bool = False
    confidence: float = 1.0
    stability_score: float = 0.0
    language_code: Optional[str] = None
    raw_data: Optional[Dict] = None


class ASRProvider(ABC):
    """Abstract Base Class for streaming real-time ASR providers."""

    @abstractmethod
    async def start(self, language: str) -> None:
        """Connects and starts the recognition session for the given language code."""
        pass

    @abstractmethod
    async def send_audio(self, chunk: bytes) -> None:
        """Sends a binary PCM audio chunk to the upstream recognition engine."""
        pass

    @abstractmethod
    def events(self) -> AsyncIterator[ASREvent]:
        """Asynchronously yields normalized ASREvent objects."""
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Signals upstream engine to flush remaining audio buffers and finalize."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Gracefully closes upstream connection and resources."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Returns True if the provider is currently connected."""
        pass


class TranslationProvider(ABC):
    """Abstract Base Class for text translation providers."""

    @abstractmethod
    async def translate(
        self,
        text: str,
        src: str,
        tgt: str,
        glossary: Optional[Dict[str, str]] = None,
    ) -> str:
        """Translates text from src language to tgt language, applying glossary overrides."""
        pass


class TTSProvider(ABC):
    """Abstract Base Class for text-to-speech providers."""

    @abstractmethod
    async def synthesize(self, text: str, lang: str) -> bytes:
        """Synthesizes text into raw audio bytes (e.g. WAV)."""
        pass
