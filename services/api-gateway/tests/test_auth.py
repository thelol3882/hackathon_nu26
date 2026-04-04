"""Tests for api_gateway.core.auth -- password hashing, JWT creation & decoding."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_SECRET = "test-secret-key-for-testing-32bytes!"
_FAKE_EXPIRY = 60


class _FakeSettings:
    jwt_secret: str = _FAKE_SECRET
    jwt_expiry_minutes = _FAKE_EXPIRY


def _patch():
    return patch("api_gateway.core.config.get_settings", return_value=_FakeSettings())


# ---------------------------------------------------------------------------
# hash_password
# ---------------------------------------------------------------------------


class TestHashPassword:
    def test_hash_returns_bcrypt(self):
        with _patch():
            from api_gateway.core.auth import hash_password

            hashed = hash_password("my-password")
            assert hashed.startswith("$2b$")

    def test_hash_empty_password(self):
        with _patch():
            from api_gateway.core.auth import hash_password

            hashed = hash_password("")
            assert hashed.startswith("$2b$")

    def test_hash_long_password(self):
        with _patch():
            from api_gateway.core.auth import hash_password

            hashed = hash_password("a" * 500)
            assert hashed.startswith("$2b$")


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------


class TestVerifyPassword:
    def test_verify_correct_password(self):
        with _patch():
            from api_gateway.core.auth import hash_password, verify_password

            hashed = hash_password("correct")
            assert verify_password("correct", hashed) is True

    def test_verify_wrong_password(self):
        with _patch():
            from api_gateway.core.auth import hash_password, verify_password

            hashed = hash_password("correct")
            assert verify_password("wrong", hashed) is False


# ---------------------------------------------------------------------------
# create_access_token / _decode_token
# ---------------------------------------------------------------------------


class TestJWT:
    def test_create_and_decode_roundtrip(self):
        with _patch():
            from api_gateway.core.auth import _decode_token, create_access_token

            uid = uuid.uuid4()
            token = create_access_token(uid, "admin")
            payload = _decode_token(token)

            assert payload["sub"] == str(uid)
            assert payload["role"] == "admin"

    def test_token_has_exp_claim(self):
        with _patch():
            from api_gateway.core.auth import create_access_token

            uid = uuid.uuid4()
            token = create_access_token(uid, "viewer")
            payload = pyjwt.decode(token, _FAKE_SECRET, algorithms=["HS256"])
            assert "exp" in payload

    def test_decode_expired_token_401(self):
        with _patch():
            from api_gateway.core.auth import _decode_token

            expired_payload = {
                "sub": str(uuid.uuid4()),
                "role": "admin",
                "exp": datetime.now(UTC) - timedelta(hours=1),
            }
            token = pyjwt.encode(expired_payload, _FAKE_SECRET, algorithm="HS256")

            with pytest.raises(HTTPException) as exc_info:
                _decode_token(token)
            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail.lower()

    def test_decode_invalid_token_401(self):
        with _patch():
            from api_gateway.core.auth import _decode_token

            with pytest.raises(HTTPException) as exc_info:
                _decode_token("not.a.valid.token")
            assert exc_info.value.status_code == 401
            assert "invalid" in exc_info.value.detail.lower()

    def test_decode_wrong_secret_401(self):
        with _patch():
            from api_gateway.core.auth import _decode_token

            payload = {
                "sub": str(uuid.uuid4()),
                "role": "admin",
                "exp": datetime.now(UTC) + timedelta(hours=1),
            }
            token = pyjwt.encode(payload, "wrong-secret-key-that-is-32bytes!", algorithm="HS256")

            with pytest.raises(HTTPException) as exc_info:
                _decode_token(token)
            assert exc_info.value.status_code == 401
