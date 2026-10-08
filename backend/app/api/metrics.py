from typing import Any, Dict
from fastapi import APIRouter
from app.store import memory_store

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/summary")
async def get_metrics_summary() -> Dict[str, Any]:
    """Returns aggregate p50 and p95 latency metrics grouped by provider and metric kind."""
    aggregates = memory_store.get_aggregate_metrics()
    return {
        "status": "ok",
        "aggregates": aggregates,
    }
