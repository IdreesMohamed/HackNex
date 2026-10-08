import time
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Dict, List, Optional, Tuple

from app.config import settings
from app.languages import get_language_config
from app.stability.text_utils import (
    calculate_stability_score,
    compute_word_lcp,
    has_sentence_boundary,
    is_translation_rewrite,
    tokenize_words,
)


@dataclass
class CommitDecision:
    """Represents the scheduling decision for an incoming hypothesis."""

    should_translate: bool
    text_to_translate: str
    is_final: bool
    committed_text: str
    stability_score: float
    trigger_reason: str
    cached_translation: Optional[str] = None


@dataclass
class SegmentState:
    """Internal state tracked per utterance segment."""

    segment_id: str
    window: Deque[str] = field(default_factory=deque)
    last_committed_text: str = ""
    last_translated_text: str = ""
    last_translation_emitted: str = ""
    first_pending_time: float = 0.0
    last_translation_time: float = 0.0
    rewrite_count: int = 0
    translation_call_count: int = 0


class AdaptiveStabilityScheduler:
    """Adaptive Stability Scheduler using word-level LCP, sentence boundary,

    max-wait timeout, and debounce guards.
    """

    def __init__(
        self,
        source_language: str = "en-IN",
        k: Optional[int] = None,
        min_words: Optional[int] = None,
        commit_words: Optional[int] = None,
        debounce_ms: Optional[int] = None,
        max_wait_ms: Optional[int] = None,
        clock_func: Optional[Callable[[], float]] = None,
        cache_capacity: int = 1000,
    ):
        self.clock = clock_func or time.time
        self.cache_capacity = cache_capacity
        self._cache: OrderedDict[Tuple[str, str, str], str] = OrderedDict()
        self._segments: Dict[str, SegmentState] = {}

        # Resolve tuning based on source language if provided
        lang_cfg = get_language_config(source_language)
        self.k = k if k is not None else (lang_cfg.stab_k if lang_cfg else settings.stab_k)
        self.min_words = (
            min_words
            if min_words is not None
            else (lang_cfg.stab_min_words if lang_cfg else settings.stab_min_words)
        )
        self.commit_words = (
            commit_words
            if commit_words is not None
            else (lang_cfg.stab_commit_words if lang_cfg else settings.stab_commit_words)
        )
        self.debounce_ms = (
            debounce_ms
            if debounce_ms is not None
            else (lang_cfg.stab_debounce_ms if lang_cfg else settings.stab_debounce_ms)
        )
        self.max_wait_ms = (
            max_wait_ms
            if max_wait_ms is not None
            else (lang_cfg.stab_max_wait_ms if lang_cfg else settings.stab_max_wait_ms)
        )

    def _get_segment(self, segment_id: str) -> SegmentState:
        if segment_id not in self._segments:
            state = SegmentState(segment_id=segment_id)
            state.window = deque(maxlen=self.k)
            state.first_pending_time = self.clock()
            self._segments[segment_id] = state
        return self._segments[segment_id]

    def feed_hypothesis(
        self,
        segment_id: str,
        hypothesis: str,
        is_final: bool,
        src: str = "en-IN",
        tgt: str = "hi-IN",
    ) -> CommitDecision:
        """Processes an incoming ASR hypothesis and determines whether to trigger translation."""
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

        # 1. Rule 1: ASR Final Flag
        if is_final:
            state.last_committed_text = clean_text
            state.window.clear()
            cached = self._lookup_cache(src, tgt, clean_text)
            return CommitDecision(
                should_translate=True,
                text_to_translate=clean_text,
                is_final=True,
                committed_text=clean_text,
                stability_score=1.0,
                trigger_reason="final",
                cached_translation=cached,
            )

        # Append to sliding window
        state.window.append(clean_text)
        if state.first_pending_time == 0.0:
            state.first_pending_time = now

        # 2. Compute Longest Common Prefix (LCP) across window
        if len(state.window) < self.k:
            # Not enough hypotheses in window yet to establish stability
            stability_score = calculate_stability_score("", clean_text)
            return CommitDecision(
                should_translate=False,
                text_to_translate="",
                is_final=False,
                committed_text="",
                stability_score=stability_score,
                trigger_reason="window_warming",
            )

        lcp = compute_word_lcp(list(state.window))
        stability_score = calculate_stability_score(lcp, clean_text)
        lcp_word_count = len(tokenize_words(lcp))

        # Check debounce timer (no more than 1 call per debounce_ms per segment)
        time_since_last_translation = (now - state.last_translation_time) * 1000
        is_debounced = time_since_last_translation >= self.debounce_ms

        trigger_reason = "none"
        should_commit = False

        # 3. Rule 2: Word Count threshold
        if lcp_word_count >= self.commit_words and lcp != state.last_translated_text:
            trigger_reason = "commit_words"
            should_commit = True

        # 4. Rule 3: Sentence boundary punctuation (. ? ! ।)
        elif (
            has_sentence_boundary(lcp)
            and lcp_word_count >= self.min_words
            and lcp != state.last_translated_text
        ):
            trigger_reason = "sentence_boundary"
            should_commit = True

        # 5. Rule 4: Max-wait timeout forcing commit
        elapsed_pending_ms = (now - state.first_pending_time) * 1000
        if not should_commit and elapsed_pending_ms >= self.max_wait_ms and lcp_word_count >= self.min_words:
            if lcp != state.last_translated_text:
                trigger_reason = "max_wait"
                should_commit = True

        # Enforce debounce guard and text novelty
        if should_commit and is_debounced and lcp != state.last_translated_text:
            state.last_committed_text = lcp
            cached = self._lookup_cache(src, tgt, lcp)
            return CommitDecision(
                should_translate=True,
                text_to_translate=lcp,
                is_final=False,
                committed_text=lcp,
                stability_score=stability_score,
                trigger_reason=trigger_reason,
                cached_translation=cached,
            )

        return CommitDecision(
            should_translate=False,
            text_to_translate="",
            is_final=False,
            committed_text=lcp,
            stability_score=stability_score,
            trigger_reason=trigger_reason if should_commit else "none",
        )

    def record_translation_result(
        self,
        segment_id: str,
        source_text: str,
        translated_text: str,
        src: str = "en-IN",
        tgt: str = "hi-IN",
    ) -> None:
        """Records translation output, checks for rewrites, and stores in cache."""
        now = self.clock()
        state = self._get_segment(segment_id)
        state.last_translation_time = now
        state.last_translated_text = source_text
        state.translation_call_count += 1

        # Check rewrite
        if state.last_translation_emitted:
            if is_translation_rewrite(state.last_translation_emitted, translated_text):
                state.rewrite_count += 1

        state.last_translation_emitted = translated_text
        state.first_pending_time = now  # Reset pending timer

        # Cache entry
        self._add_to_cache(src, tgt, source_text, translated_text)

    def get_metrics(self, segment_id: str) -> Dict:
        """Returns tracking metrics for a segment."""
        state = self._get_segment(segment_id)
        return {
            "rewrite_count": state.rewrite_count,
            "translation_call_count": state.translation_call_count,
            "last_committed_text": state.last_committed_text,
        }

    def _lookup_cache(self, src: str, tgt: str, text: str) -> Optional[str]:
        key = (src, tgt, text.strip())
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _add_to_cache(self, src: str, tgt: str, text: str, translated: str) -> None:
        key = (src, tgt, text.strip())
        self._cache[key] = translated
        self._cache.move_to_end(key)
        if len(self._cache) > self.cache_capacity:
            self._cache.popitem(last=False)
