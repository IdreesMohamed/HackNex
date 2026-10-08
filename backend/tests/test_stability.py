import pytest
from app.stability.scheduler import AdaptiveStabilityScheduler
from app.stability.baseline import FixedIntervalBaselineScheduler
from app.stability.text_utils import compute_word_lcp, has_sentence_boundary, is_translation_rewrite


class FakeClock:
    """Controllable clock for deterministic stability testing."""

    def __init__(self, start_time: float = 1000.0):
        self.current_time = start_time

    def time(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


def test_word_lcp():
    assert compute_word_lcp([]) == ""
    assert compute_word_lcp(["வணக்கம்"]) == "வணக்கம்"
    assert compute_word_lcp(["நான் சென்னைக்கு", "நான் சென்னைக்கு போகிறேன்", "நான் சென்னைக்கு செல்கிறேன்"]) == "நான் சென்னைக்கு"
    assert compute_word_lcp(["hello world", "hello there", "hello"]) == "hello"
    assert compute_word_lcp(["apple", "banana"]) == ""


def test_sentence_boundary_detection():
    assert has_sentence_boundary("This is a sentence.") is True
    assert has_sentence_boundary("Is this a sentence?") is True
    assert has_sentence_boundary("Hello!") is True
    assert has_sentence_boundary("यह एक वाक्य है।") is True  # Devanagari danda
    assert has_sentence_boundary("यह अधूरा वाक्य है") is False


def test_translation_rewrite_detection():
    # Append continuation is NOT a rewrite
    assert is_translation_rewrite("I am going", "I am going to Chennai") is False
    # Changing the subject/verb IS a rewrite
    assert is_translation_rewrite("He is going to Chennai", "They will arrive at Mumbai") is True


def test_empty_and_whitespace_input():
    clock = FakeClock()
    scheduler = AdaptiveStabilityScheduler(clock_func=clock.time)
    d1 = scheduler.feed_hypothesis("seg-1", "", is_final=False)
    assert d1.should_translate is False
    assert d1.trigger_reason == "empty"

    d2 = scheduler.feed_hypothesis("seg-1", "   ", is_final=False)
    assert d2.should_translate is False


def test_final_always_translates():
    clock = FakeClock()
    scheduler = AdaptiveStabilityScheduler(clock_func=clock.time)

    # Even single word final should translate
    d = scheduler.feed_hypothesis("seg-1", "வணக்கம்", is_final=True)
    assert d.should_translate is True
    assert d.is_final is True
    assert d.text_to_translate == "வணக்கம்"
    assert d.trigger_reason == "final"


def test_lcp_window_warming():
    clock = FakeClock()
    scheduler = AdaptiveStabilityScheduler(k=3, clock_func=clock.time)

    # 1st hypothesis: warming (len < 3)
    d1 = scheduler.feed_hypothesis("seg-1", "நான்", is_final=False)
    assert d1.should_translate is False
    assert d1.trigger_reason == "window_warming"

    # 2nd hypothesis: warming
    clock.advance(0.1)
    d2 = scheduler.feed_hypothesis("seg-1", "நான் சென்னைக்கு", is_final=False)
    assert d2.should_translate is False
    assert d2.trigger_reason == "window_warming"


def test_commit_words_rule():
    clock = FakeClock()
    # commit_words = 4, min_words = 3, k = 3
    scheduler = AdaptiveStabilityScheduler(k=3, commit_words=4, min_words=3, debounce_ms=100, clock_func=clock.time)

    scheduler.feed_hypothesis("seg-1", "one two three four five", is_final=False)
    clock.advance(0.05)
    scheduler.feed_hypothesis("seg-1", "one two three four five six", is_final=False)
    clock.advance(0.05)

    # 3rd hypothesis with 4 common words stable prefix
    d = scheduler.feed_hypothesis("seg-1", "one two three four five seven", is_final=False)
    assert d.should_translate is True
    assert d.trigger_reason == "commit_words"
    assert d.committed_text == "one two three four five"


def test_sentence_boundary_commit_with_danda():
    clock = FakeClock()
    scheduler = AdaptiveStabilityScheduler(k=2, commit_words=10, min_words=3, debounce_ms=100, clock_func=clock.time)

    scheduler.feed_hypothesis("seg-1", "यह एक अच्छा दिन है।", is_final=False)
    clock.advance(0.05)
    d = scheduler.feed_hypothesis("seg-1", "यह एक अच्छा दिन है। और हम", is_final=False)

    assert d.should_translate is True
    assert d.trigger_reason == "sentence_boundary"
    assert "दिन है।" in d.committed_text


def test_max_wait_forced_commit():
    clock = FakeClock()
    # max_wait_ms = 1000, min_words = 3, commit_words = 10 (will not trigger on words)
    scheduler = AdaptiveStabilityScheduler(k=2, commit_words=10, min_words=3, max_wait_ms=1000, debounce_ms=100, clock_func=clock.time)

    scheduler.feed_hypothesis("seg-1", "one two three four", is_final=False)
    clock.advance(0.2)
    scheduler.feed_hypothesis("seg-1", "one two three four tentative", is_final=False)

    # Advance time past max-wait
    clock.advance(1.2)
    d = scheduler.feed_hypothesis("seg-1", "one two three four another_tentative", is_final=False)

    assert d.should_translate is True
    assert d.trigger_reason == "max_wait"
    assert d.committed_text == "one two three four"


def test_debounce_guard():
    clock = FakeClock()
    scheduler = AdaptiveStabilityScheduler(k=2, commit_words=3, min_words=3, debounce_ms=500, clock_func=clock.time)

    scheduler.feed_hypothesis("seg-1", "one two three four", is_final=False)
    d1 = scheduler.feed_hypothesis("seg-1", "one two three four five", is_final=False)
    assert d1.should_translate is True

    # Record translation at t=1000.0
    scheduler.record_translation_result("seg-1", "one two three four", "1 2 3 4")

    # Try commit again after only 100ms (debounce is 500ms)
    clock.advance(0.1)
    scheduler.feed_hypothesis("seg-1", "one two three four five six", is_final=False)
    d2 = scheduler.feed_hypothesis("seg-1", "one two three four five six seven", is_final=False)
    assert d2.should_translate is False  # Blocked by debounce guard

    # Advance past debounce window (total 600ms)
    clock.advance(0.5)
    d3 = scheduler.feed_hypothesis("seg-1", "one two three four five six seven eight", is_final=False)
    assert d3.should_translate is True


def test_identical_text_does_not_repeat():
    clock = FakeClock()
    scheduler = AdaptiveStabilityScheduler(k=2, commit_words=3, debounce_ms=100, clock_func=clock.time)

    scheduler.feed_hypothesis("seg-1", "one two three four", is_final=False)
    d1 = scheduler.feed_hypothesis("seg-1", "one two three four", is_final=False)
    assert d1.should_translate is True

    scheduler.record_translation_result("seg-1", "one two three four", "translation 1")

    # Next hypothesis with identical stable prefix
    clock.advance(0.2)
    scheduler.feed_hypothesis("seg-1", "one two three four", is_final=False)
    d2 = scheduler.feed_hypothesis("seg-1", "one two three four", is_final=False)
    assert d2.should_translate is False  # Already translated


def test_rewrite_counting():
    clock = FakeClock()
    scheduler = AdaptiveStabilityScheduler(clock_func=clock.time)

    # First translation
    scheduler.record_translation_result("seg-1", "hello", "Namaste")
    metrics1 = scheduler.get_metrics("seg-1")
    assert metrics1["rewrite_count"] == 0

    # Normal extension: "Namaste, how are you" (not a rewrite)
    scheduler.record_translation_result("seg-1", "hello how are you", "Namaste aap kaise hain")
    metrics2 = scheduler.get_metrics("seg-1")
    assert metrics2["rewrite_count"] == 0

    # Complete change of translation: "Good evening" -> rewrite!
    scheduler.record_translation_result("seg-1", "good evening", "Shubh sandhya sabhi ko")
    metrics3 = scheduler.get_metrics("seg-1")
    assert metrics3["rewrite_count"] == 1


def test_baseline_scheduler_comparison():
    clock = FakeClock()
    baseline = FixedIntervalBaselineScheduler(fixed_interval_ms=500, clock_func=clock.time)

    d1 = baseline.feed_hypothesis("seg-1", "one", is_final=False)
    assert d1.should_translate is True  # First call allowed

    baseline.record_translation_result("seg-1", "one", "ek")

    # 200ms later -> rejected (not reached 500ms)
    clock.advance(0.2)
    d2 = baseline.feed_hypothesis("seg-1", "one two", is_final=False)
    assert d2.should_translate is False

    # 400ms more (total 600ms) -> allowed
    clock.advance(0.4)
    d3 = baseline.feed_hypothesis("seg-1", "one two", is_final=False)
    assert d3.should_translate is True
    assert d3.trigger_reason == "fixed_interval"
