import time

import jwt
import pytest

from app.auth.jwt_tokens import InvalidTokenError, TokenType, create_access_token, create_refresh_token, decode_token
from app.config import Settings


@pytest.fixture
def settings():
    return Settings(jwt_secret_key="a" * 32, access_token_expire_minutes=15, refresh_token_expire_days=30)


def test_access_token_round_trips_the_user_id(settings):
    token = create_access_token("user-123", settings)
    assert decode_token(token, TokenType.ACCESS, settings) == "user-123"


def test_refresh_token_round_trips_the_user_id(settings):
    token = create_refresh_token("user-456", settings)
    assert decode_token(token, TokenType.REFRESH, settings) == "user-456"


def test_access_token_rejected_as_a_refresh_token(settings):
    token = create_access_token("user-123", settings)
    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.REFRESH, settings)


def test_tampered_signature_is_rejected(settings):
    token = create_access_token("user-123", settings)
    other_settings = Settings(jwt_secret_key="b" * 32)
    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.ACCESS, other_settings)


def test_garbage_token_is_rejected(settings):
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-jwt", TokenType.ACCESS, settings)


def test_expired_token_is_rejected(settings):
    payload = {"sub": "user-123", "type": TokenType.ACCESS.value, "iat": time.time() - 120, "exp": time.time() - 60}
    expired = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_token(expired, TokenType.ACCESS, settings)
