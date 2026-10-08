import pytest
import respx
import httpx
from app.config import settings
from app.errors import BhashaLiveException, ErrorCode
from app.providers.sarvam_translate import SarvamTranslationProvider
from app.providers.sarvam_asr import SarvamASRProvider


@pytest.mark.asyncio
async def test_sarvam_translate_success(monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "mock-test-key-12345")
    provider = SarvamTranslationProvider()

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(settings.sarvam_translate_url).respond(
            status_code=200,
            json={
                "request_id": "test_req_01",
                "translated_text": "I will go to Chennai tomorrow.",
                "source_language_code": "ta-IN",
            },
        )

        result = await provider.translate(
            text="நான் நாளைக்கு சென்னைக்கு போகிறேன்.",
            src="ta-IN",
            tgt="en-IN",
        )

        assert result == "I will go to Chennai tomorrow."
        assert route.called
        request = route.calls.last.request
        assert request.headers["api-subscription-key"] == "mock-test-key-12345"


@pytest.mark.asyncio
async def test_sarvam_translate_empty_text():
    provider = SarvamTranslationProvider(api_key="mock-key")
    result = await provider.translate("", "ta-IN", "en-IN")
    assert result == ""
    result_spaces = await provider.translate("   ", "ta-IN", "en-IN")
    assert result_spaces == ""


@pytest.mark.asyncio
async def test_sarvam_translate_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", None)
    provider = SarvamTranslationProvider()

    with pytest.raises(BhashaLiveException) as exc_info:
        await provider.translate("Hello", "en-IN", "hi-IN")
    assert exc_info.value.code == ErrorCode.PROVIDER_NOT_CONFIGURED


@pytest.mark.asyncio
async def test_sarvam_translate_401_auth_failure(monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "invalid-key")
    provider = SarvamTranslationProvider()

    with respx.mock:
        respx.post(settings.sarvam_translate_url).respond(status_code=401, text="Unauthorized")
        with pytest.raises(BhashaLiveException) as exc_info:
            await provider.translate("Hello", "en-IN", "hi-IN")
        assert exc_info.value.code == ErrorCode.PROVIDER_NOT_CONFIGURED


@pytest.mark.asyncio
async def test_sarvam_translate_429_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-key")
    provider = SarvamTranslationProvider()

    with respx.mock:
        respx.post(settings.sarvam_translate_url).respond(status_code=429, text="Rate limit exceeded")
        with pytest.raises(BhashaLiveException) as exc_info:
            await provider.translate("Hello", "en-IN", "hi-IN")
        assert exc_info.value.code == ErrorCode.RATE_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_sarvam_translate_retry_on_server_error(monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-key")
    provider = SarvamTranslationProvider()

    with respx.mock as respx_mock:
        # First call fails with 503, second succeeds with 200
        respx_mock.post(settings.sarvam_translate_url).side_effect = [
            httpx.Response(status_code=503, text="Service Unavailable"),
            httpx.Response(status_code=200, json={"translated_text": "Retried success"}),
        ]

        result = await provider.translate("Testing retry", "en-IN", "hi-IN")
        assert result == "Retried success"


def test_sarvam_asr_message_parser():
    provider = SarvamASRProvider(api_key="test-key")

    # Partial transcript
    raw_partial = '{"type": "transcript", "text": "வணக்கம்", "is_final": false, "confidence": 0.9}'
    event = provider._parse_message(raw_partial)
    assert event is not None
    assert event.text == "வணக்கம்"
    assert event.is_final is False
    assert event.confidence == 0.9

    # Final transcript
    raw_final = '{"type": "transcript", "text": "வணக்கம் நண்பர்களே", "is_final": true, "confidence": 0.98}'
    event = provider._parse_message(raw_final)
    assert event is not None
    assert event.text == "வணக்கம் நண்பர்களே"
    assert event.is_final is True

    # Unknown or VAD event
    raw_vad = '{"type": "events", "name": "START_SPEECH"}'
    assert provider._parse_message(raw_vad) is None

    # Malformed JSON
    assert provider._parse_message("not valid json") is None
