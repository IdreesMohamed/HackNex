import asyncio
import json
from typing import AsyncIterator, Dict, List, Optional
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.providers.base import ASREvent, ASRProvider, TranslationProvider
from app.ws.pipeline import SessionPipeline


class FakeASRProvider(ASRProvider):
    def __init__(self, events_to_emit: Optional[List[ASREvent]] = None):
        self._events = events_to_emit or []
        self._connected = False
        self._audio_chunks: List[bytes] = []

    async def start(self, language: str) -> None:
        self._connected = True

    async def send_audio(self, chunk: bytes) -> None:
        self._audio_chunks.append(chunk)

    async def events(self) -> AsyncIterator[ASREvent]:
        for ev in self._events:
            await asyncio.sleep(0.01)
            yield ev

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected


class FakeTranslationProvider(TranslationProvider):
    def __init__(self, failure: bool = False):
        self.failure = failure
        self.call_count = 0

    async def translate(
        self,
        text: str,
        src: str,
        tgt: str,
        glossary: Optional[Dict[str, str]] = None,
    ) -> str:
        self.call_count += 1
        if self.failure:
            raise RuntimeError("Simulated translation upstream timeout")
        # Deterministic mock translation
        return f"[Translated to {tgt}]: {text}"


@pytest.mark.asyncio
async def test_ws_pipeline_flow_and_stable_segment_id():
    """Validates that all partials and final for an utterance share the EXACT same segment_id."""
    sent_events: List[Dict] = []

    async def mock_send(data: Dict):
        sent_events.append(data)

    # 3 interim events and 1 final
    asr_events = [
        ASREvent(text="one", is_final=False, confidence=0.8),
        ASREvent(text="one two three", is_final=False, confidence=0.85),
        ASREvent(text="one two three four five six", is_final=False, confidence=0.9),
        ASREvent(text="one two three four five six seven.", is_final=True, confidence=0.98),
    ]

    fake_asr = FakeASRProvider(events_to_emit=asr_events)
    fake_tr = FakeTranslationProvider()

    pipeline = SessionPipeline(
        session_id="test-session-stable-id",
        source_language="en-IN",
        target_language="ta-IN",
        send_json=mock_send,
        asr_provider=fake_asr,
        translation_provider=fake_tr,
    )

    await pipeline.start()
    await pipeline.push_audio(b"\x00\x00" * 1600)  # 100ms silence

    # Wait for ASR events and translation tasks to execute
    await asyncio.sleep(0.3)
    await pipeline.handle_end()

    # Verify event types received
    event_types = [e["type"] for e in sent_events]
    assert "session.status" in event_types
    assert "transcript.partial" in event_types
    assert "transcript.final" in event_types
    assert "translation.final" in event_types

    # Collect all segment_ids for the first utterance
    transcript_partials = [e for e in sent_events if e["type"] == "transcript.partial"]
    transcript_finals = [e for e in sent_events if e["type"] == "transcript.final"]
    translation_finals = [e for e in sent_events if e["type"] == "translation.final"]

    assert len(transcript_finals) == 1
    assert len(translation_finals) == 1

    final_seg_id = transcript_finals[0]["segment_id"]

    # All partials for this utterance must have the exact same segment_id
    for part in transcript_partials:
        assert part["segment_id"] == final_seg_id

    # The final translation must also share the exact same segment_id
    assert translation_finals[0]["segment_id"] == final_seg_id


@pytest.mark.asyncio
async def test_ws_pipeline_translation_failure_resilience():
    """Validates that a translation error does not crash the session and preserves source captions."""
    sent_events: List[Dict] = []

    async def mock_send(data: Dict):
        sent_events.append(data)

    asr_events = [
        ASREvent(text="testing failure mode", is_final=True, confidence=0.95),
    ]
    fake_asr = FakeASRProvider(events_to_emit=asr_events)
    fake_tr = FakeTranslationProvider(failure=True)  # Translation always fails

    pipeline = SessionPipeline(
        session_id="test-session-degraded",
        source_language="en-IN",
        target_language="hi-IN",
        send_json=mock_send,
        asr_provider=fake_asr,
        translation_provider=fake_tr,
    )

    await pipeline.start()
    await asyncio.sleep(0.15)
    await pipeline.handle_end()

    event_types = [e["type"] for e in sent_events]
    # Source caption must be emitted successfully
    assert "transcript.final" in event_types

    # Should report degraded status and retryable error
    degraded_status = [
        e for e in sent_events if e["type"] == "session.status" and e.get("state") == "degraded"
    ]
    assert len(degraded_status) >= 1

    errors = [e for e in sent_events if e["type"] == "error"]
    assert len(errors) >= 1
    assert errors[0]["retryable"] is True


def test_ws_endpoint_rejection_when_unconfigured(monkeypatch):
    """Checks that WebSocket endpoint returns honest PROVIDER_NOT_CONFIGURED when keys missing."""
    monkeypatch.setattr(settings, "sarvam_api_key", None)
    monkeypatch.setattr(settings, "azure_speech_key", None)

    client = TestClient(app)
    with client.websocket_connect("/ws/translate") as ws:
        # Send session.start
        ws.send_json(
            {
                "type": "session.start",
                "source_language": "ta-IN",
                "target_language": "en-IN",
            }
        )
        response = ws.receive_json()
        assert response["type"] == "error"
        assert response["code"] == "PROVIDER_NOT_CONFIGURED"


def test_ws_endpoint_unsupported_language():
    client = TestClient(app)
    with client.websocket_connect("/ws/translate") as ws:
        ws.send_json(
            {
                "type": "session.start",
                "source_language": "fr-FR",  # Unsupported
                "target_language": "en-IN",
            }
        )
        response = ws.receive_json()
        assert response["type"] == "error"
        assert response["code"] == "UNSUPPORTED_LANGUAGE"
