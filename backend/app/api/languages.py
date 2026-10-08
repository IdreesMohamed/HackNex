from fastapi import APIRouter
from app.languages import SUPPORTED_LANGUAGES
from app.schemas import LanguageItem, LanguagesResponse

router = APIRouter(tags=["Languages"])


@router.get("/languages", response_model=LanguagesResponse)
async def list_languages() -> LanguagesResponse:
    """Lists supported languages and their validation status."""
    items = [
        LanguageItem(
            code=cfg.code,
            name=cfg.name,
            native_name=cfg.native_name,
            validated=cfg.validated,
            is_verb_final=cfg.is_verb_final,
        )
        for cfg in SUPPORTED_LANGUAGES.values()
    ]
    return LanguagesResponse(languages=items)
