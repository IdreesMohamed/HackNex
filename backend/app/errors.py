from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    INVALID_SESSION = "INVALID_SESSION"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    UNAUTHORIZED_ORIGIN = "UNAUTHORIZED_ORIGIN"
    INVALID_AUDIO_CHUNK = "INVALID_AUDIO_CHUNK"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TRANSLATION_FAILED = "TRANSLATION_FAILED"
    ASR_DISCONNECTED = "ASR_DISCONNECTED"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    MALFORMED_EVENT = "MALFORMED_EVENT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


SAFE_ERROR_MESSAGES = {
    ErrorCode.PROVIDER_NOT_CONFIGURED: "Translation or speech provider is not configured. Please check server settings.",
    ErrorCode.INVALID_SESSION: "Session ID is invalid or not found.",
    ErrorCode.SESSION_EXPIRED: "Session has exceeded maximum duration and expired.",
    ErrorCode.UNAUTHORIZED_ORIGIN: "Origin not permitted.",
    ErrorCode.INVALID_AUDIO_CHUNK: "Audio chunk format or size is invalid.",
    ErrorCode.RATE_LIMIT_EXCEEDED: "Rate limit exceeded. Please wait before creating a new session.",
    ErrorCode.TRANSLATION_FAILED: "Translation service encountered a temporary error.",
    ErrorCode.ASR_DISCONNECTED: "Speech recognition upstream connection lost. Attempting reconnection.",
    ErrorCode.UNSUPPORTED_LANGUAGE: "The selected language code is not supported.",
    ErrorCode.MALFORMED_EVENT: "The client message could not be processed.",
    ErrorCode.INTERNAL_ERROR: "An unexpected server error occurred.",
}


class BhashaLiveException(Exception):
    """Base exception returning only sanitized, safe messages to clients."""

    def __init__(
        self,
        code: ErrorCode,
        safe_message: Optional[str] = None,
        retryable: bool = False,
        detail: Optional[str] = None,
    ):
        self.code = code
        self.safe_message = safe_message or SAFE_ERROR_MESSAGES.get(code, "A service error occurred.")
        self.retryable = retryable
        self.detail = detail  # For internal logging only
        super().__init__(self.safe_message)
