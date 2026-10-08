import time
from fastapi import APIRouter
from app.languages import is_language_supported
from app.errors import BhashaLiveException, ErrorCode
from app.schemas import TranslateRequest, TranslateResponse
from app.providers.sarvam_translate import SarvamTranslationProvider

router = APIRouter(tags=["Translation"])
translator = SarvamTranslationProvider()


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(req: TranslateRequest) -> TranslateResponse:
    """Utility endpoint to translate arbitrary text using the primary translation provider."""
    if not is_language_supported(req.source_language) or not is_language_supported(req.target_language):
        raise BhashaLiveException(
            code=ErrorCode.UNSUPPORTED_LANGUAGE,
            safe_message="One or both selected languages are not supported.",
            retryable=False,
        )

    t0 = time.perf_counter()
    translated_text = await translator.translate(
        text=req.text,
        src=req.source_language,
        tgt=req.target_language,
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return TranslateResponse(
        translated_text=translated_text,
        source_language=req.source_language,
        target_language=req.target_language,
        provider="sarvam",
        latency_ms=latency_ms,
    )
