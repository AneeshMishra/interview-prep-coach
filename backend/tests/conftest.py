"""Shared pytest fixtures. Currently just one: keep the app's rate limits
(app/rate_limit.py) from interfering with the rest of the test suite,
which makes far more requests per test than any real caller would in the
same window. Dedicated rate-limit tests (test_rate_limit_endpoints.py)
override these same dependency keys with a deliberately tiny limiter to
exercise the 429 path — this fixture's restore-on-teardown is scoped only
to the three keys it touches, so it never clobbers those per-test overrides."""
import pytest

from app.main import app
from app.rate_limit import RateLimiter, get_auth_rate_limiter, get_llm_rate_limiter, get_upload_rate_limiter

_LIMITER_GETTERS = (get_auth_rate_limiter, get_upload_rate_limiter, get_llm_rate_limiter)


@pytest.fixture(autouse=True)
def _generous_rate_limits():
    permissive = lambda: RateLimiter(max_requests=1_000_000, window_seconds=60)  # noqa: E731
    prior = {getter: app.dependency_overrides.get(getter) for getter in _LIMITER_GETTERS}
    for getter in _LIMITER_GETTERS:
        app.dependency_overrides[getter] = permissive

    yield

    for getter, override in prior.items():
        if override is None:
            app.dependency_overrides.pop(getter, None)
        else:
            app.dependency_overrides[getter] = override
