import os
import re
from typing import Any, List, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_REFERENCE = re.compile(r"^process\.env\.([A-Z0-9_]+)$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    @model_validator(mode="before")
    @classmethod
    def resolve_render_env_references(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        resolved = dict(values)
        for key, value in resolved.items():
            if not isinstance(value, str):
                continue
            match = _ENV_REFERENCE.fullmatch(value.strip())
            if not match:
                continue
            referenced = os.getenv(match.group(1))
            if referenced is not None:
                resolved[key] = referenced
            elif key in {"cors_origins", "allowed_ws_origins"}:
                resolved[key] = "*"
            else:
                resolved[key] = ""
        return resolved

    # --- App ---
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "*"
    allowed_ws_origins: str = "*"
    session_token_secret: str = "bhashalive_default_dev_secret_change_in_prod"

    # --- Sarvam (Primary) ---
    sarvam_api_key: Optional[str] = None
    sarvam_asr_url: str = "wss://api.sarvam.ai/speech-to-text-realtime/ws"
    sarvam_asr_model: str = "saaras:v3-realtime"
    sarvam_translate_url: str = "https://api.sarvam.ai/translate"
    sarvam_translate_model: str = "mayura:v1"
    sarvam_tts_url: str = "https://api.sarvam.ai/text-to-speech"

    # --- Azure (Fallback) ---
    azure_speech_key: Optional[str] = None
    azure_speech_region: Optional[str] = None
    azure_translator_key: Optional[str] = None
    azure_translator_region: Optional[str] = None
    azure_translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"

    # --- Storage ---
    database_url: str = "postgresql+asyncpg://bhasha:bhasha@postgres:5432/bhashalive"
    redis_url: str = "redis://redis:6379/0"

    # --- Monitoring ---
    sentry_dsn: Optional[str] = None

    # --- Feature flags ---
    enable_fallback: bool = True
    enable_persistence: bool = True
    enable_tts: bool = False
    enable_glossary: bool = True
    enable_two_way: bool = False
    store_raw_audio: bool = False

    # --- Stability scheduler defaults ---
    stab_k: int = 3
    stab_min_words: int = 3
    stab_commit_words: int = 6
    stab_debounce_ms: int = 300
    stab_max_wait_ms: int = 1500
    scheduler_mode: str = "adaptive"  # 'adaptive' or 'fixed500'

    # --- Limits ---
    rate_limit_sessions_per_min: int = 10
    max_session_seconds: int = 1800
    max_audio_chunk_bytes: int = 65536

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.cors_origins:
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_ws_origins_list(self) -> List[str]:
        if not self.allowed_ws_origins:
            return ["*"]
        return [origin.strip() for origin in self.allowed_ws_origins.split(",") if origin.strip()]

    @property
    def is_sarvam_asr_configured(self) -> bool:
        return bool(self.sarvam_api_key and self.sarvam_api_key.strip() and self.sarvam_api_key != "replace_with_your_key")

    @property
    def is_sarvam_translate_configured(self) -> bool:
        return bool(self.sarvam_api_key and self.sarvam_api_key.strip() and self.sarvam_api_key != "replace_with_your_key")

    @property
    def is_sarvam_tts_configured(self) -> bool:
        return bool(self.sarvam_api_key and self.sarvam_api_key.strip() and self.sarvam_api_key != "replace_with_your_key")

    @property
    def is_azure_speech_configured(self) -> bool:
        return bool(
            self.azure_speech_key
            and self.azure_speech_key.strip()
            and self.azure_speech_region
            and self.azure_speech_region.strip()
        )

    @property
    def is_azure_translator_configured(self) -> bool:
        return bool(self.azure_translator_key and self.azure_translator_key.strip())


settings = Settings()
