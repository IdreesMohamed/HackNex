import statistics
import time
from typing import Any, Dict, List, Optional


class MemoryStore:
    """In-memory data store used when PostgreSQL persistence is disabled

    or during offline testing. Provides hard-deletion and aggregate calculations.
    """

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.segments: Dict[str, List[Dict[str, Any]]] = {}
        self.metrics: Dict[str, List[Dict[str, Any]]] = {}
        self.glossary: Dict[str, Dict[str, Any]] = {}

    def create_session(
        self,
        session_id: str,
        source_language: str,
        target_language: str,
        provider: str = "sarvam",
        status: str = "connected",
    ) -> Dict[str, Any]:
        session = {
            "id": session_id,
            "source_language": source_language,
            "target_language": target_language,
            "provider": provider,
            "status": status,
            "created_at": time.time(),
            "ended_at": None,
        }
        self.sessions[session_id] = session
        self.segments[session_id] = []
        self.metrics[session_id] = []
        return session

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        if session_id in self.sessions:
            self.sessions[session_id].update(kwargs)
            return self.sessions[session_id]
        return None

    def save_segment(self, session_id: str, segment: Dict[str, Any]) -> None:
        if session_id not in self.segments:
            self.segments[session_id] = []
        self.segments[session_id].append(segment)

    def get_segments(self, session_id: str) -> List[Dict[str, Any]]:
        return self.segments.get(session_id, [])

    def save_metric(self, session_id: str, metric: Dict[str, Any]) -> None:
        if session_id not in self.metrics:
            self.metrics[session_id] = []
        self.metrics[session_id].append(metric)

    def get_session_metrics(self, session_id: str) -> List[Dict[str, Any]]:
        return self.metrics.get(session_id, [])

    def delete_session(self, session_id: str) -> bool:
        """Hard-deletes session, all its segments, and all its metrics."""
        found = False
        if session_id in self.sessions:
            del self.sessions[session_id]
            found = True
        if session_id in self.segments:
            del self.segments[session_id]
            found = True
        if session_id in self.metrics:
            del self.metrics[session_id]
            found = True
        return found

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Calculates aggregate p50 and p95 latency metrics grouped by provider and kind."""
        kinds: Dict[str, List[float]] = {}
        for session_id, m_list in self.metrics.items():
            for m in m_list:
                k = m.get("kind", "latency")
                v = m.get("value_ms")
                if v is not None:
                    if k not in kinds:
                        kinds[k] = []
                    kinds[k].append(float(v))

        summary: Dict[str, Any] = {}
        for kind, values in kinds.items():
            if not values:
                continue
            sorted_vals = sorted(values)
            p50 = statistics.median(sorted_vals)
            p95_idx = int(0.95 * len(sorted_vals))
            p95 = sorted_vals[min(p95_idx, len(sorted_vals) - 1)]
            summary[kind] = {
                "count": len(values),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
            }
        return summary


memory_store = MemoryStore()
