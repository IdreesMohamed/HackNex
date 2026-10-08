import uuid
from typing import Dict, List, Optional
from app.schemas import GlossaryTermCreate, GlossaryTermResponse
from app.store import memory_store


class GlossaryManager:
    """Manages custom terminology and named entities to preserve domain names,

    places, and organizations during translation.
    """

    def __init__(self):
        self._terms: Dict[str, Dict] = {}

    def add_term(self, term_data: GlossaryTermCreate) -> GlossaryTermResponse:
        term_id = str(uuid.uuid4())
        item = {
            "id": term_id,
            "term": term_data.term.strip(),
            "source_language": term_data.source_language,
            "target_language": term_data.target_language,
            "preferred_translation": term_data.preferred_translation.strip(),
        }
        self._terms[term_id] = item
        return GlossaryTermResponse(**item)

    def list_terms(
        self,
        src: Optional[str] = None,
        tgt: Optional[str] = None,
    ) -> List[GlossaryTermResponse]:
        results = []
        for t in self._terms.values():
            if src and t["source_language"] != src:
                continue
            if tgt and t["target_language"] != tgt:
                continue
            results.append(GlossaryTermResponse(**t))
        return results

    def get_replacement_map(self, src: str, tgt: str) -> Dict[str, str]:
        """Returns a lookup dictionary of term -> preferred_translation for a given language pair."""
        mapping = {}
        for t in self._terms.values():
            if t["source_language"] == src and t["target_language"] == tgt:
                mapping[t["term"]] = t["preferred_translation"]
        return mapping


glossary_manager = GlossaryManager()
