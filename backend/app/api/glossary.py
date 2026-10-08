from typing import List, Optional
from fastapi import APIRouter, Query

from app.glossary import glossary_manager
from app.schemas import GlossaryTermCreate, GlossaryTermResponse

router = APIRouter(prefix="/glossary", tags=["Glossary"])


@router.post("", response_model=GlossaryTermResponse, status_code=201)
async def create_glossary_term(term: GlossaryTermCreate) -> GlossaryTermResponse:
    """Adds a custom domain term or entity translation override."""
    return glossary_manager.add_term(term)


@router.get("", response_model=List[GlossaryTermResponse])
async def get_glossary_terms(
    source_language: Optional[str] = Query(None),
    target_language: Optional[str] = Query(None),
) -> List[GlossaryTermResponse]:
    """Retrieves all registered glossary terms."""
    return glossary_manager.list_terms(src=source_language, tgt=target_language)
