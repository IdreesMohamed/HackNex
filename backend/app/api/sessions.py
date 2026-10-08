import datetime
import uuid
from typing import List
from fastapi import APIRouter, Request

from app.config import settings
from app.db.repo import delete_session_hard, get_session, get_session_segments
from app.errors import BhashaLiveException, ErrorCode
from app.languages import is_language_supported
from app.schemas import (
    CreateSessionRequest,
    SegmentResponse,
    SessionMetricsResponse,
    SessionResponse,
)
from app.security import create_ws_token, rate_limiter
from app.store import memory_store

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(req: CreateSessionRequest, request: Request) -> SessionResponse:
    """Creates a new translation session, returns signed ws_token."""
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise BhashaLiveException(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            safe_message="Rate limit exceeded for session creation. Please try again later.",
            retryable=True,
        )

    if not is_language_supported(req.source_language) or not is_language_supported(req.target_language):
        raise BhashaLiveException(
            code=ErrorCode.UNSUPPORTED_LANGUAGE,
            safe_message="Unsupported language pair specified.",
            retryable=False,
        )

    session_id = str(uuid.uuid4())
    expires_seconds = settings.max_session_seconds
    expires_dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_seconds)
    ws_token = create_ws_token(session_id, expires_in_seconds=expires_seconds)

    memory_store.create_session(
        session_id=session_id,
        source_language=req.source_language,
        target_language=req.target_language,
        provider="sarvam",
        status="created",
    )

    return SessionResponse(
        session_id=session_id,
        ws_token=ws_token,
        source_language=req.source_language,
        target_language=req.target_language,
        status="created",
        expires_at=expires_dt.isoformat() + "Z",
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_details(session_id: str) -> SessionResponse:
    """Returns details for an active or past session."""
    sess = await get_session(session_id)
    if not sess:
        raise BhashaLiveException(
            code=ErrorCode.INVALID_SESSION,
            safe_message="Session not found.",
            retryable=False,
        )

    ws_token = create_ws_token(session_id, expires_in_seconds=300)
    return SessionResponse(
        session_id=sess["id"],
        ws_token=ws_token,
        source_language=sess["source_language"],
        target_language=sess["target_language"],
        status=sess.get("status", "connected"),
        expires_at=datetime.datetime.utcnow().isoformat() + "Z",
    )


@router.get("/{session_id}/segments", response_model=List[SegmentResponse])
async def get_segments_for_session(session_id: str) -> List[SegmentResponse]:
    """Retrieves all finalized segments for a session."""
    segments = await get_session_segments(session_id)
    results = []
    for s in segments:
        created_str = (
            datetime.datetime.fromtimestamp(s["created_at"]).isoformat()
            if isinstance(s.get("created_at"), (int, float))
            else str(s.get("created_at", ""))
        )
        results.append(
            SegmentResponse(
                segment_id=s.get("segment_id") or s.get("id", ""),
                sequence_no=s.get("sequence_no", 1),
                source_text=s.get("source_text", ""),
                translated_text=s.get("translated_text", ""),
                confidence=s.get("confidence", 1.0),
                stability_score=s.get("stability_score", 1.0),
                rewrite_count=s.get("rewrite_count", 0),
                created_at=created_str,
            )
        )
    return results


@router.get("/{session_id}/metrics", response_model=SessionMetricsResponse)
async def get_metrics_for_session(session_id: str) -> SessionMetricsResponse:
    """Returns latency and quality metrics for a session."""
    sess = await get_session(session_id)
    if not sess:
        raise BhashaLiveException(
            code=ErrorCode.INVALID_SESSION,
            safe_message="Session not found.",
            retryable=False,
        )

    raw_metrics = memory_store.get_session_metrics(session_id)
    segments = await get_session_segments(session_id)

    total_rewrites = sum(s.get("rewrite_count", 0) for s in segments)
    e2e_latencies = [m["value_ms"] for m in raw_metrics if m.get("kind") == "end_to_end_latency_ms"]

    first_latency = e2e_latencies[0] if e2e_latencies else None
    final_latency = e2e_latencies[-1] if e2e_latencies else None

    return SessionMetricsResponse(
        session_id=session_id,
        first_caption_latency_ms=first_latency,
        final_latency_ms=final_latency,
        rewrite_count=total_rewrites,
        translation_call_count=len(segments),
    )


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Hard-deletes the session, its segments, and its metrics for privacy compliance."""
    deleted = await delete_session_hard(session_id)
    if not deleted:
        raise BhashaLiveException(
            code=ErrorCode.INVALID_SESSION,
            safe_message="Session not found to delete.",
            retryable=False,
        )
    return {"status": "ok", "deleted": True, "session_id": session_id}
