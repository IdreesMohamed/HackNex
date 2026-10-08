import logging
import pytest
from app.security import create_ws_token, verify_ws_token, is_origin_allowed, rate_limiter
from app.logging_conf import SecretRedactionFilter
from app.config import settings


def test_token_creation_and_verification():
    session_id = "test-session-12345"
    token = create_ws_token(session_id, expires_in_seconds=300)
    assert token is not None

    valid, extracted_id = verify_ws_token(token, expected_session_id=session_id)
    assert valid is True
    assert extracted_id == session_id

    # Wrong expected session ID
    valid, extracted_id = verify_ws_token(token, expected_session_id="different-id")
    assert valid is False

    # Tampered token
    tampered = token[:-4] + "abcd"
    valid, _ = verify_ws_token(tampered)
    assert valid is False

    # Expired token
    expired_token = create_ws_token(session_id, expires_in_seconds=-10)
    valid, _ = verify_ws_token(expired_token)
    assert valid is False


def test_origin_validation():
    allowed = ["http://localhost:5173", "http://localhost:3000"]
    assert is_origin_allowed("http://localhost:5173", allowed) is True
    assert is_origin_allowed("http://localhost:3000/", allowed) is True
    assert is_origin_allowed("https://malicious.site", allowed) is False
    assert is_origin_allowed(None, allowed) is True  # Non-browser client


def test_secret_redaction_in_logging():
    filter_ = SecretRedactionFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Connecting with api-subscription-key: secretkey123456789 to upstream",
        args=(),
        exc_info=None,
    )
    filter_.filter(record)
    assert "secretkey123456789" not in record.msg
    assert "[REDACTED]" in record.msg


def test_rate_limiter():
    client_ip = "192.168.1.50"
    limiter = rate_limiter
    limiter.limit = 3
    limiter.requests.clear()

    assert limiter.is_allowed(client_ip) is True
    assert limiter.is_allowed(client_ip) is True
    assert limiter.is_allowed(client_ip) is True
    assert limiter.is_allowed(client_ip) is False  # Exceeded limit
