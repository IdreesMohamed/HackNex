import asyncio
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import GlossaryTermModel, MetricModel, SegmentModel, SessionModel
from app.db.session import async_session_factory
from app.store import memory_store

logger = logging.getLogger("bhashalive.db.repo")

# Background writer queue for non-blocking persistence
_persist_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=1000)
_writer_task: Optional[asyncio.Task] = None


async def start_background_writer() -> None:
    """Starts the background DB persistence worker."""
    global _writer_task
    if _writer_task is None or _writer_task.done():
        _writer_task = asyncio.create_task(_background_writer_loop())


async def _background_writer_loop() -> None:
    """Consumes write tasks asynchronously off the critical path."""
    while True:
        try:
            item = await _persist_queue.get()
            item_type = item.get("type")

            if not async_session_factory or not settings.enable_persistence:
                _persist_queue.task_done()
                continue

            async with async_session_factory() as session:
                try:
                    if item_type == "segment":
                        data = item["data"]
                        model = SegmentModel(
                            id=data.get("id"),
                            session_id=data["session_id"],
                            sequence_no=data.get("sequence_no", 1),
                            source_text=data["source_text"],
                            translated_text=data["translated_text"],
                            confidence=data.get("confidence", 1.0),
                            stability_score=data.get("stability_score", 1.0),
                            rewrite_count=data.get("rewrite_count", 0),
                        )
                        session.add(model)
                        await session.commit()

                    elif item_type == "metric":
                        data = item["data"]
                        model = MetricModel(
                            session_id=data["session_id"],
                            segment_id=data.get("segment_id"),
                            kind=data["kind"],
                            value_ms=data["value_ms"],
                            provider=data.get("provider", "sarvam"),
                        )
                        session.add(model)
                        await session.commit()

                except Exception as e:
                    await session.rollback()
                    logger.warning(f"Background DB writer failed to persist item ({item_type}): {e}")

            _persist_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in background writer loop: {e}")


def enqueue_segment(segment_data: Dict[str, Any]) -> None:
    """Enqueues segment for background persistence and caches in MemoryStore."""
    memory_store.save_segment(segment_data["session_id"], segment_data)
    try:
        _persist_queue.put_nowait({"type": "segment", "data": segment_data})
    except asyncio.QueueFull:
        logger.warning("Background persist queue full; dropping segment DB write")


def enqueue_metric(metric_data: Dict[str, Any]) -> None:
    """Enqueues metric for background persistence and caches in MemoryStore."""
    memory_store.save_metric(metric_data["session_id"], metric_data)
    try:
        _persist_queue.put_nowait({"type": "metric", "data": metric_data})
    except asyncio.QueueFull:
        logger.warning("Background persist queue full; dropping metric DB write")


async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    # Check memory store first
    mem = memory_store.get_session(session_id)
    if mem:
        return mem

    if async_session_factory and settings.enable_persistence:
        try:
            async with async_session_factory() as session:
                result = await session.execute(select(SessionModel).where(SessionModel.id == session_id))
                row = result.scalar_one_or_none()
                if row:
                    return {
                        "id": row.id,
                        "source_language": row.source_language,
                        "target_language": row.target_language,
                        "provider": row.provider,
                        "status": row.status,
                        "created_at": row.created_at.timestamp() if row.created_at else None,
                        "ended_at": row.ended_at.timestamp() if row.ended_at else None,
                    }
        except Exception as e:
            logger.warning(f"DB error fetching session {session_id}: {e}")

    return None


async def get_session_segments(session_id: str) -> List[Dict[str, Any]]:
    # Prefer memory store
    mem_segs = memory_store.get_segments(session_id)
    if mem_segs:
        return mem_segs

    if async_session_factory and settings.enable_persistence:
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(SegmentModel).where(SegmentModel.session_id == session_id).order_by(SegmentModel.sequence_no)
                )
                rows = result.scalars().all()
                return [
                    {
                        "segment_id": r.id,
                        "sequence_no": r.sequence_no,
                        "source_text": r.source_text,
                        "translated_text": r.translated_text,
                        "confidence": r.confidence,
                        "stability_score": r.stability_score,
                        "rewrite_count": r.rewrite_count,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning(f"DB error fetching segments for session {session_id}: {e}")

    return []


async def delete_session_hard(session_id: str) -> bool:
    """Hard-deletes session and all its associated data for privacy compliance."""
    # Delete from memory store
    mem_deleted = memory_store.delete_session(session_id)

    db_deleted = False
    if async_session_factory and settings.enable_persistence:
        try:
            async with async_session_factory() as session:
                stmt = delete(SessionModel).where(SessionModel.id == session_id)
                res = await session.execute(stmt)
                await session.commit()
                if res.rowcount and res.rowcount > 0:
                    db_deleted = True
        except Exception as e:
            logger.warning(f"DB error hard-deleting session {session_id}: {e}")

    return mem_deleted or db_deleted
