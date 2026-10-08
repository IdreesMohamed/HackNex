import logging
import json
import re
import sys
from typing import Any, Dict
from app.config import settings

SECRET_PATTERNS = [
    re.compile(r"api[-_]?subscription[-_]?key[=:\s]+(['\"]?)([\w\-]+)\1", re.IGNORECASE),
    re.compile(r"bearer\s+([\w\-.]+)", re.IGNORECASE),
    re.compile(r"key[=:\s]+(['\"]?)([\w\-]{16,})\1", re.IGNORECASE),
]


class SecretRedactionFilter(logging.Filter):
    """Redacts API keys and sensitive tokens from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redact(v) if isinstance(v, str) else v for v in record.args)
        return True

    @staticmethod
    def redact(text: str) -> str:
        if not text:
            return text
        result = text
        # Redact configured known secrets if present
        for secret in [settings.sarvam_api_key, settings.azure_speech_key, settings.azure_translator_key]:
            if secret and len(secret) > 4 and secret in result:
                result = result.replace(secret, "[REDACTED]")

        # Redact regex patterns
        for pattern in SECRET_PATTERNS:
            result = pattern.sub(r"[REDACTED]", result)
        return result


class JSONFormatter(logging.Formatter):
    """Outputs structured JSON log records."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_obj.update(record.extra)
        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging() -> None:
    """Configures structured logging and optional Sentry initialization."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SecretRedactionFilter())
    root_logger.addHandler(handler)

    # Sentry integration
    if settings.sentry_dsn and settings.sentry_dsn.strip():
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_logging = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            )
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                integrations=[FastApiIntegration(), sentry_logging],
                traces_sample_rate=0.1,
                environment=settings.app_env,
            )
            root_logger.info("Sentry monitoring initialized successfully")
        except Exception as e:
            root_logger.warning(f"Failed to initialize Sentry: {e}")
