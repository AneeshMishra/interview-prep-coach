"""
In-memory rate limiting for auth, upload and LLM-calling endpoints. Redis
is deferred (CLAUDE.md), and rate-limit counters are transient abuse
guards, not state that needs to survive a restart — an in-memory,
per-process limiter is the right fit, unlike sessions (see
app/auth/jwt_tokens.py) which must never live only in a process dict.

Two keying strategies:
  - rate_limit_by_ip: for endpoints reached before a user is authenticated
    (OAuth login/callback/refresh).
  - rate_limit_by_user: for endpoints that already require Depends(get_current_user)
    — keyed per account, not per IP, so one abusive account can't hide
    behind a shared NAT/IP and unrelated users on the same IP are never
    penalized for someone else's activity.
"""
import threading
import time
from functools import lru_cache
from typing import Callable

from fastapi import Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.db.models import User


class RateLimiter:
    """Fixed-window counter, keyed per caller. Not sliding/leaky-bucket —
    a caller can burst up to max_requests near a window boundary and again
    just after it resets. That's an acceptable trade-off for an abuse
    guard (CLAUDE.md: simple working implementation over speculative
    precision); it is not a billing-grade quota mechanism."""

    def __init__(self, max_requests: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._windows: dict[str, tuple[float, int]] = {}  # key -> (window_start, count)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Raise HTTPException(429) if `key` has exceeded its limit for the
        current window; otherwise record this call and return."""
        now = self._clock()
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            if now - window_start >= self.window_seconds:
                window_start, count = now, 0

            if count >= self.max_requests:
                retry_after = window_start + self.window_seconds - now
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please slow down and try again shortly.",
                    headers={"Retry-After": str(max(1, int(retry_after) + 1))},
                )

            self._windows[key] = (window_start, count + 1)

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


@lru_cache
def get_auth_rate_limiter() -> RateLimiter:
    settings = get_settings()
    return RateLimiter(settings.rate_limit_auth_max, settings.rate_limit_auth_window_seconds)


@lru_cache
def get_upload_rate_limiter() -> RateLimiter:
    settings = get_settings()
    return RateLimiter(settings.rate_limit_upload_max, settings.rate_limit_upload_window_seconds)


@lru_cache
def get_llm_rate_limiter() -> RateLimiter:
    settings = get_settings()
    return RateLimiter(settings.rate_limit_llm_max, settings.rate_limit_llm_window_seconds)


def rate_limit_by_ip(get_limiter: Callable[[], RateLimiter]):
    """Dependency factory: rate limit by client IP. Use for endpoints
    reached before there's an authenticated user to key on."""

    def dependency(request: Request, limiter: RateLimiter = Depends(get_limiter)) -> None:
        host = request.client.host if request.client else "unknown"
        limiter.check(f"ip:{host}")

    return dependency


def rate_limit_by_user(get_limiter: Callable[[], RateLimiter]):
    """Dependency factory: rate limit by signed-in user. Depending on
    get_current_user here piggybacks on FastAPI's per-request dependency
    cache — the endpoint's own Depends(get_current_user) and this one
    resolve to a single DB lookup, not two."""

    def dependency(
        current_user: User = Depends(get_current_user), limiter: RateLimiter = Depends(get_limiter)
    ) -> None:
        limiter.check(f"user:{current_user.id}")

    return dependency
