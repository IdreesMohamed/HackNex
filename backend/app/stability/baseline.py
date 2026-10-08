import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from app.stability.scheduler import CommitDecision
from app.stability.text_utils import calculate_stability_score, is_translation_rewrite


@dataclass
class BaselineSegmentState:
    segment_id: str
    last_translation_time: float = 0.0
    last_translated_text: str = ""
    last_translation_emitted: str = ""
    rewrite_count: int = 0
    translation_call_count: int = 0


class FixedIntervalBaselineScheduler:
    """Fixed-interval baseline scheduler for ablation comparisons.

    Translates the latest hypothesis periodically (every fixed_interval_ms, default 500ms)
    without computing LCP stability.
    """

    def __init__(
        self,
        fixed_interval_ms: int = 500,
        clock_func: Optional[Callable[[], float]] = None,
    ):
        self.interval_ms = fixed_interval_ms
        self.clock = clock_func or time.time
        self._segments: Dict[str, BaselineSegmentState] = {}

    def _get_segment(self, segment_id: str) -> BaselineSegmentState:
        if segment_id not in self._segments:
            self._segments[segment_id] = BaselineSegmentState(segment_id=segment_id)
        return self._segments[segment_id]

    def feed_hypothesis(
        self,
        segment_id: str,
        hypothesis: str,
        is_final: bool,
        src: str = "en-IN",
        tgt: str = "hi-IN",
    ) -> CommitDecision:
        now = self.clock()
        state = self._get_segment(segment_id)
        clean_text = hypothesis.strip()

        if not clean_text:
            return CommitDecision(
                should_translate=False,
                text_to_translate="",
                is_final=is_final,
                committed_text="",
                stability_score=0.0,
                trigger_reason="empty",
            )

        if is_final:
            return CommitDecision(
                should_translate=True,
                text_to_translate=clean_text,
                is_final=True,
                committed_text=clean_text,
                stability_score=1.0,
                trigger_reason="final",
            )

        time_since_last_call = (now - state.last_translation_time) * 1000
        if time_since_last_call >= self.interval_ms and clean_text != state.last_translated_text:
            return CommitDecision(
                should_translate=True,
                text_to_translate=clean_text,
                is_final=False,
                committed_text=clean_text,
                stability_score=0.5,
                trigger_reason="fixed_interval",
            )

        return CommitDecision(
            should_translate=False,
            text_to_translate="",
            is_final=False,
            committed_text="",
            stability_score=0.0,
            trigger_reason="none",
        )

    def record_translation_result(
        self,
        segment_id: str,
        source_text: str,
        translated_text: str,
        src: str = "en-IN",
        tgt: str = "hi-IN",
    ) -> None:
        now = self.clock()
        state = self._get_segment(segment_id)
        state.last_translation_time = now
        state.last_translated_text = source_text
        state.translation_call_count += 1

        if state.last_translation_emitted:
            if is_translation_rewrite(state.last_translation_emitted, translated_text):
                state.rewrite_count += 1

        state.last_translation_emitted = translated_text

    def get_metrics(self, segment_id: str) -> Dict:
        state = self._get_segment(segment_id)
        return {
            "rewrite_count": state.rewrite_count,
            "translation_call_count": state.translation_call_count,
        }
