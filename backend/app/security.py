import hmac
import hashlib
import time
import base64
import json
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from app.config import settings
from app.errors import BhashaLiveException, ErrorCode


class InMemoryRateLimiter:
    """Sliding window rate limiter for REST session creation."""

    def __init__(self, limit: int = 10, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        # Clean older entries
        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > window_start]
        if len(self.requests[client_ip]) >= self.limit:
            return False
        self.requests[client_ip].append(now)
        return True


rate_limiter = InMemoryRateLimiter(
    limit=settings.rate_limit_sessions_per_min,
    window_seconds=60,
)


def create_ws_token(session_id: str, expires_in_seconds: int = 1800) -> str:
    """Creates a signed, time-limited token for WebSocket authentication."""
    expires_at = int(time.time()) + expires_in_seconds
    payload = f"{session_id}:{expires_at}"
    secret = settings.session_token_secret.encode("utf-8")
    signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token_data = {"s": session_id, "e": expires_at, "sig": signature}
    token_str = json.dumps(token_data)
    return base64.urlsafe_b64encode(token_str.encode("utf-8")).decode("utf-8")


def verify_ws_token(token: str, expected_session_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Verifies HMAC signature and expiration of a WebSocket token."""
    if not token:
        return False, None
    try:
        decoded_bytes = base64.urlsafe_b64decode(token.encode("utf-8"))
        data = json.loads(decoded_bytes.decode("utf-8"))
        session_id = data.get("s")
        expires_at = data.get("e")
        signature = data.get("sig")

        if not session_id or not expires_at or not signature:
            return False, None

        if time.time() > expires_at:
            return False, None

        if expected_session_id and session_id != expected_session_id:
            return False, None

        payload = f"{session_id}:{expires_at}"
        secret = settings.session_token_secret.encode("utf-8")
        expected_sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return False, None

        return True, session_id
    except Exception:
        return False, None


def is_origin_allowed(origin: Optional[str], allowed_origins: List[str]) -> bool:
    """Checks whether an Origin header matches the allowed origin list."""
    if not allowed_origins or "*" in allowed_origins:
        return True
    if not origin:
        # In non-browser environments or direct curl/test scripts origin might be None
        return True
    origin = origin.strip().rstrip("/")
    for allowed in allowed_origins:
        if origin == allowed.strip().rstrip("/"):
            return True
    return False
