from typing import Dict, List, Optional
from pydantic import BaseModel


class LanguageConfig(BaseModel):
    code: str
    name: str
    native_name: str
    is_verb_final: bool
    validated: bool
    # Stability scheduler tuning per language
    stab_k: int
    stab_min_words: int
    stab_commit_words: int
    stab_debounce_ms: int
    stab_max_wait_ms: int


SUPPORTED_LANGUAGES: Dict[str, LanguageConfig] = {
    "en-IN": LanguageConfig(
        code="en-IN",
        name="Indian English",
        native_name="English",
        is_verb_final=False,
        validated=True,
        stab_k=2,
        stab_min_words=2,
        stab_commit_words=5,
        stab_debounce_ms=250,
        stab_max_wait_ms=1200,
    ),
    "hi-IN": LanguageConfig(
        code="hi-IN",
        name="Hindi",
        native_name="हिन्दी",
        is_verb_final=True,
        validated=True,
        stab_k=3,
        stab_min_words=3,
        stab_commit_words=6,
        stab_debounce_ms=300,
        stab_max_wait_ms=1500,
    ),
    "ta-IN": LanguageConfig(
        code="ta-IN",
        name="Tamil",
        native_name="தமிழ்",
        is_verb_final=True,
        validated=True,
        stab_k=3,
        stab_min_words=4,
        stab_commit_words=7,
        stab_debounce_ms=350,
        stab_max_wait_ms=1800,
    ),
    "te-IN": LanguageConfig(
        code="te-IN",
        name="Telugu",
        native_name="తెలుగు",
        is_verb_final=True,
        validated=False,
        stab_k=3,
        stab_min_words=4,
        stab_commit_words=7,
        stab_debounce_ms=350,
        stab_max_wait_ms=1800,
    ),
    "kn-IN": LanguageConfig(
        code="kn-IN",
        name="Kannada",
        native_name="ಕನ್ನಡ",
        is_verb_final=True,
        validated=False,
        stab_k=3,
        stab_min_words=4,
        stab_commit_words=7,
        stab_debounce_ms=350,
        stab_max_wait_ms=1800,
    ),
    "ml-IN": LanguageConfig(
        code="ml-IN",
        name="Malayalam",
        native_name="മലയാളം",
        is_verb_final=True,
        validated=False,  # Needs quality gate review
        stab_k=3,
        stab_min_words=4,
        stab_commit_words=7,
        stab_debounce_ms=350,
        stab_max_wait_ms=1800,
    ),
}

# Azure language code mappings where BCP-47 differs
AZURE_SPEECH_LANG_MAP: Dict[str, str] = {
    "en-IN": "en-IN",
    "hi-IN": "hi-IN",
    "ta-IN": "ta-IN",
    "te-IN": "te-IN",
    "kn-IN": "kn-IN",
    "ml-IN": "ml-IN",
}

AZURE_TRANSLATOR_LANG_MAP: Dict[str, str] = {
    "en-IN": "en",
    "hi-IN": "hi",
    "ta-IN": "ta",
    "te-IN": "te",
    "kn-IN": "kn",
    "ml-IN": "ml",
}


def is_language_supported(code: str) -> bool:
    return code in SUPPORTED_LANGUAGES


def is_pair_validated(src: str, tgt: str) -> bool:
    if src not in SUPPORTED_LANGUAGES or tgt not in SUPPORTED_LANGUAGES:
        return False
    return SUPPORTED_LANGUAGES[src].validated and SUPPORTED_LANGUAGES[tgt].validated


def get_language_config(code: str) -> Optional[LanguageConfig]:
    return SUPPORTED_LANGUAGES.get(code)
