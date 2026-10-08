import time
import httpx
from fastapi import APIRouter
from app.config import settings
from app.schemas import HealthResponse, ProviderHealthItem, ProvidersHealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Returns basic service health status."""
    return HealthResponse()


@router.get("/health/providers", response_model=ProvidersHealthResponse)
async def get_providers_health() -> ProvidersHealthResponse:
    """Returns honest configuration and reachability status for all external providers."""

    # 1. Sarvam ASR
    sarvam_asr_configured = settings.is_sarvam_asr_configured
    sarvam_asr_reachable = False
    sarvam_asr_latency: float | None = None
    if sarvam_asr_configured:
        try:
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get("https://api.sarvam.ai/")
                sarvam_asr_latency = round((time.perf_counter() - t0) * 1000, 2)
                sarvam_asr_reachable = res.status_code < 500
        except Exception:
            sarvam_asr_reachable = False

    # 2. Sarvam Translate
    sarvam_tr_configured = settings.is_sarvam_translate_configured
    sarvam_tr_reachable = sarvam_asr_reachable  # Shares domain
    sarvam_tr_latency = sarvam_asr_latency

    # 3. Sarvam TTS
    sarvam_tts_configured = settings.is_sarvam_tts_configured
    sarvam_tts_reachable = sarvam_asr_reachable
    sarvam_tts_latency = sarvam_asr_latency

    # 4. Azure Speech
    azure_speech_configured = settings.is_azure_speech_configured
    azure_speech_reachable = False
    azure_speech_latency: float | None = None
    if azure_speech_configured and settings.azure_speech_region:
        try:
            t0 = time.perf_counter()
            endpoint = f"https://{settings.azure_speech_region}.api.cognitive.microsoft.com/"
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(endpoint)
                azure_speech_latency = round((time.perf_counter() - t0) * 1000, 2)
                azure_speech_reachable = res.status_code < 500
        except Exception:
            azure_speech_reachable = False

    # 5. Azure Translator
    azure_tr_configured = settings.is_azure_translator_configured
    azure_tr_reachable = False
    azure_tr_latency: float | None = None
    if azure_tr_configured:
        try:
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(settings.azure_translator_endpoint)
                azure_tr_latency = round((time.perf_counter() - t0) * 1000, 2)
                azure_tr_reachable = res.status_code < 500
        except Exception:
            azure_tr_reachable = False

    return ProvidersHealthResponse(
        sarvam_asr=ProviderHealthItem(
            configured=sarvam_asr_configured,
            reachable=sarvam_asr_reachable,
            latency_ms=sarvam_asr_latency,
        ),
        sarvam_translate=ProviderHealthItem(
            configured=sarvam_tr_configured,
            reachable=sarvam_tr_reachable,
            latency_ms=sarvam_tr_latency,
        ),
        sarvam_tts=ProviderHealthItem(
            configured=sarvam_tts_configured,
            reachable=sarvam_tts_reachable,
            latency_ms=sarvam_tts_latency,
        ),
        azure_speech=ProviderHealthItem(
            configured=azure_speech_configured,
            reachable=azure_speech_reachable,
            latency_ms=azure_speech_latency,
        ),
        azure_translator=ProviderHealthItem(
            configured=azure_tr_configured,
            reachable=azure_tr_reachable,
            latency_ms=azure_tr_latency,
        ),
    )
