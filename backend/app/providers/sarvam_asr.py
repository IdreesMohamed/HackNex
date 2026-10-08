import asyncio
import base64
import json
import logging
import urllib.parse
from collections import deque
from typing import AsyncIterator, Optional
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from app.config import settings
from app.errors import BhashaLiveException, ErrorCode
from app.providers.base import ASRProvider, ASREvent

logger = logging.getLogger("bhashalive.provider.sarvam_asr")


class SarvamASRProvider(ASRProvider):
    """Streaming ASR adapter for Sarvam Saaras realtime WebSocket API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        buffer_size: int = 20,  # Buffer last ~2 seconds (at 100ms/chunk) for reconnect replay
    ):
        self.api_key = api_key or settings.sarvam_api_key
        self.base_url = base_url or settings.sarvam_asr_url
        self.model = model or settings.sarvam_asr_model
        self.buffer_size = buffer_size

        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.language: Optional[str] = None
        self._audio_buffer: deque[bytes] = deque(maxlen=self.buffer_size)
        self._connected: bool = False
        self._closed: bool = False

    @property
    def is_connected(self) -> bool:
        if not self._connected or self.ws is None:
            return False
        state = getattr(self.ws, "state", None)
        if state is not None:
            return state.name == "OPEN"
        return not getattr(self.ws, "closed", False)

    def _build_ws_url(self, language: str) -> str:
        params = {
            "language_code": language,
            "model": self.model,
            "stream_type": "balanced",
            "mode": "transcribe",
            "endpointing": "vad",
            "encoding": "linear16",
            "sample_rate": "16000",
        }
        query_string = urllib.parse.urlencode(params)
        base = self.base_url.rstrip("?")
        return f"{base}?{query_string}"

    async def start(self, language: str) -> None:
        """Connects to Sarvam realtime WebSocket endpoint with reconnect retries."""
        if not self.api_key or not self.api_key.strip() or self.api_key == "replace_with_your_key":
            raise BhashaLiveException(
                code=ErrorCode.PROVIDER_NOT_CONFIGURED,
                safe_message="Sarvam ASR provider is not configured.",
                retryable=False,
                detail="Missing SARVAM_API_KEY",
            )

        self.language = language
        self._closed = False
        await self._connect_with_retry()

    async def _connect_with_retry(self, max_retries: int = 3) -> None:
        ws_url = self._build_ws_url(self.language or "ta-IN")
        headers = {"api-subscription-key": self.api_key}

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Connecting to Sarvam ASR (attempt {attempt}/{max_retries})")
                connect_kwargs = {
                    "ping_interval": 20,
                    "ping_timeout": 10,
                }
                try:
                    self.ws = await websockets.connect(
                        ws_url,
                        additional_headers=headers,
                        **connect_kwargs,
                    )
                except TypeError:
                    self.ws = await websockets.connect(
                        ws_url,
                        extra_headers=headers,
                        **connect_kwargs,
                    )
                self._connected = True
                logger.info("Successfully connected to Sarvam ASR WebSocket")

                # If we have buffered audio chunks, replay them to the newly connected socket
                if self._audio_buffer:
                    logger.info(f"Replaying {len(self._audio_buffer)} buffered audio chunks")
                    for chunk in list(self._audio_buffer):
                        await self._send_audio_frame(chunk)
                return
            except websockets.exceptions.InvalidStatusCode as e:
                status = e.status_code
                logger.error(f"Sarvam ASR handshake failed with HTTP {status}")
                if status in (401, 403, 429):
                    raise BhashaLiveException(
                        code=ErrorCode.PROVIDER_NOT_CONFIGURED if status in (401, 403) else ErrorCode.RATE_LIMIT_EXCEEDED,
                        safe_message="Upstream speech recognition service authorization or quota failure.",
                        retryable=False,
                        detail=f"Sarvam ASR handshake HTTP {status}",
                    )
                last_error = e
            except Exception as e:
                logger.warning(f"Sarvam ASR connection error (attempt {attempt}): {e}")
                last_error = e

            if attempt < max_retries:
                backoff = 0.5 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

        self._connected = False
        raise BhashaLiveException(
            code=ErrorCode.ASR_DISCONNECTED,
            safe_message="Could not establish connection to upstream speech recognition.",
            retryable=True,
            detail=f"Sarvam ASR connection exhausted retries: {last_error}",
        )

    async def send_audio(self, chunk: bytes) -> None:
        """Sends a PCM chunk in Sarvam realtime's JSON/base64 audio_input format."""
        if self._closed:
            return

        self._audio_buffer.append(chunk)

        if not self.is_connected:
            # Try to reconnect if dropped
            try:
                await self._connect_with_retry(max_retries=2)
            except Exception as e:
                logger.error(f"Failed to reconnect Sarvam ASR on send_audio: {e}")
                raise

        try:
            if self.ws:
                await self._send_audio_frame(chunk)
        except (ConnectionClosed, WebSocketException) as e:
            logger.warning(f"Send audio failed due to closed connection: {e}")
            self._connected = False
            # Attempt reconnect once
            await self._connect_with_retry(max_retries=1)
            if self.ws:
                await self._send_audio_frame(chunk)

    async def _send_audio_frame(self, chunk: bytes) -> None:
        if self.ws:
            await self.ws.send(json.dumps({
                "event": "audio_input",
                "audio": base64.b64encode(chunk).decode("ascii"),
            }))

    async def events(self) -> AsyncIterator[ASREvent]:
        """Yields parsed ASREvent objects from the upstream WebSocket stream."""
        while not self._closed:
            if not self.is_connected:
                # Wait briefly for potential reconnection
                await asyncio.sleep(0.1)
                continue

            try:
                raw_msg = await self.ws.recv()
                event = self._parse_message(raw_msg)
                if event:
                    yield event
            except ConnectionClosed:
                logger.warning("Sarvam ASR WebSocket connection closed by upstream")
                self._connected = False
                if self._closed:
                    break
                # Try to reconnect
                try:
                    await self._connect_with_retry(max_retries=3)
                except Exception as e:
                    logger.error(f"Sarvam ASR reconnect failed in event loop: {e}")
                    raise
            except Exception as e:
                logger.error(f"Error receiving event from Sarvam ASR: {e}")
                if self._closed:
                    break
                await asyncio.sleep(0.1)

    def _parse_message(self, raw_msg: str | bytes) -> Optional[ASREvent]:
        """Safely parses Sarvam WebSocket messages into a standardized ASREvent."""
        if isinstance(raw_msg, bytes):
            return None

        try:
            data = json.loads(raw_msg)
            # Sarvam realtime API uses "event" (e.g. transcript.partial, transcript.final, session.begin)
            # Legacy or alternative endpoints use "type" (e.g. transcript, data)
            msg_event = data.get("event") or data.get("type") or ""

            # Sarvam emits transcripts under event "transcript.partial", "transcript.final", "transcript", or "data"
            if msg_event in ("transcript.partial", "transcript.final", "transcript", "data"):
                text = data.get("text") or data.get("transcript") or ""
                if not text:
                    return None

                is_final = (msg_event == "transcript.final") or bool(data.get("is_final") or data.get("final", False))
                confidence = float(data.get("confidence", 1.0))
                stability_score = float(data.get("stability_score", 0.0))
                lang = data.get("language_code", self.language)

                return ASREvent(
                    text=text.strip(),
                    is_final=is_final,
                    confidence=confidence,
                    stability_score=stability_score,
                    language_code=lang,
                    raw_data=data,
                )
            elif msg_event in ("events", "vad.speech_start", "vad.speech_end"):
                logger.debug(f"Received VAD event from Sarvam: {msg_event}")
                return None
            elif msg_event == "error":
                err_msg = data.get("message", "Unknown Sarvam error")
                err_code = data.get("code")
                logger.error(f"Sarvam upstream reported error: code={err_code}, msg={err_msg}")
                return None
            else:
                logger.debug(f"Ignored Sarvam message: {msg_event}")
                return None
        except Exception as e:
            logger.warning(f"Failed to parse upstream Sarvam ASR message: {e}")
            return None

    async def flush(self) -> None:
        """Sends silence frames to trigger Sarvam VAD speech_end endpointing and flush signal."""
        if self.is_connected and self.ws:
            try:
                # Send ~1.0s of silence (16kHz 16-bit mono = 32000 bytes)
                # to trigger Sarvam VAD silence_duration_ms=1000 endpointing
                silence_chunk = b"\x00" * 3200
                for _ in range(10):
                    await self._send_audio_frame(silence_chunk)
                    await asyncio.sleep(0.01)
                await self.ws.send(json.dumps({"event": "flush"}))
            except Exception as e:
                logger.warning(f"Error sending flush frame to Sarvam ASR: {e}")

    async def close(self) -> None:
        """Closes the WebSocket gracefully."""
        self._closed = True
        self._connected = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.debug(f"Error closing Sarvam ASR connection: {e}")
        self.ws = None
