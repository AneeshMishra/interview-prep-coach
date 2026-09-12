import pytest
from fastapi import HTTPException

from app.rate_limit import RateLimiter


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_allows_up_to_max_requests_within_the_window():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=3, window_seconds=60, clock=clock)

    limiter.check("a")
    limiter.check("a")
    limiter.check("a")  # 3rd call still within the limit


def test_raises_429_once_the_limit_is_exceeded():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=2, window_seconds=60, clock=clock)

    limiter.check("a")
    limiter.check("a")
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("a")

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_retry_after_header_reflects_remaining_window_time():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=1, window_seconds=60, clock=clock)

    limiter.check("a")
    clock.advance(45)  # 15 seconds left in the window
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("a")

    retry_after = int(exc_info.value.headers["Retry-After"])
    assert 14 <= retry_after <= 16


def test_different_keys_have_independent_limits():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=1, window_seconds=60, clock=clock)

    limiter.check("user:alice")
    limiter.check("user:bob")  # bob's own limit, unaffected by alice's call

    with pytest.raises(HTTPException):
        limiter.check("user:alice")


def test_limit_resets_once_the_window_elapses():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=1, window_seconds=60, clock=clock)

    limiter.check("a")
    with pytest.raises(HTTPException):
        limiter.check("a")

    clock.advance(60)  # window has fully elapsed
    limiter.check("a")  # succeeds again


def test_reset_clears_all_keys():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=1, window_seconds=60, clock=clock)

    limiter.check("a")
    limiter.reset()
    limiter.check("a")  # succeeds again without waiting for the window
