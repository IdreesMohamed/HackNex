import pytest
from app.providers.router import CircuitBreaker, CircuitState, RoutedTranslationProvider
from app.providers.base import TranslationProvider


class FakeClock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def time(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


class MockTranslator(TranslationProvider):
    def __init__(self, name: str, should_fail: bool = False):
        self.name = name
        self.should_fail = should_fail
        self.call_count = 0

    async def translate(self, text: str, src: str, tgt: str, glossary=None) -> str:
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError(f"{self.name} failure")
        return f"[{self.name}]: {text}"


def test_circuit_breaker_state_transitions():
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=30.0, clock_func=clock.time)

    assert cb.state == CircuitState.CLOSED
    assert cb.can_attempt() is True

    # 1st failure
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_failures == 1

    # 2nd failure
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    # 3rd failure -> trips to OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_attempt() is False

    # 15 seconds later (within timeout) -> still OPEN
    clock.advance(15.0)
    assert cb.can_attempt() is False
    assert cb.state == CircuitState.OPEN

    # 35 seconds later (past timeout) -> transitions to HALF_OPEN probe
    clock.advance(20.0)
    assert cb.can_attempt() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Probe succeeds -> CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_failures == 0


def test_circuit_breaker_half_open_failure_re_trips():
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=10.0, clock_func=clock.time)

    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    clock.advance(15.0)
    assert cb.can_attempt() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Probe fails -> immediately re-trips to OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_routed_translation_automatic_failover():
    primary = MockTranslator(name="sarvam", should_fail=True)
    fallback = MockTranslator(name="azure", should_fail=False)
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=2, clock_func=clock.time)

    router = RoutedTranslationProvider(primary=primary, fallback=fallback, circuit_breaker=cb)

    # Call 1: primary fails -> falls back to azure
    res1 = await router.translate("hello", "en-IN", "ta-IN")
    assert res1 == "[azure]: hello"
    assert primary.call_count == 1
    assert fallback.call_count == 1
    assert router.active_provider_name == "azure"

    # Call 2: primary fails again -> trips breaker to OPEN
    res2 = await router.translate("world", "en-IN", "ta-IN")
    assert res2 == "[azure]: world"
    assert cb.state == CircuitState.OPEN

    # Call 3: Circuit OPEN -> skips primary completely, routes directly to azure!
    res3 = await router.translate("direct", "en-IN", "ta-IN")
    assert res3 == "[azure]: direct"
    assert primary.call_count == 2  # Not incremented on Call 3!
    assert fallback.call_count == 3
