"""Email OTP challenges stored in Redis (hashed, TTL-bound, attempt-limited)."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import cast

from django.conf import settings

from core.redis import get_redis

PURPOSE_LOGIN = "login"
PURPOSE_VERIFY_EMAIL = "verify_email"
PURPOSE_RESET = "reset_password"


class OTPError(Exception):
    pass


@dataclass
class Challenge:
    id: str
    user_id: int
    purpose: str
    code: str  # plaintext, only available right after creation (for emailing)


def _hash(challenge_id: str, code: str) -> str:
    msg = f"{challenge_id}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def _key(cid):
    return f"otp:{cid}"


def _new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def create_challenge(user, purpose: str) -> Challenge:
    r = get_redis()
    cid = secrets.token_urlsafe(24)
    code = _new_code()
    r.hset(
        _key(cid),
        mapping={
            "user_id": user.pk,
            "purpose": purpose,
            "hash": _hash(cid, code),
            "attempts": 0,
        },
    )
    r.expire(_key(cid), settings.OTP_TTL_SECONDS)
    r.set(f"{_key(cid)}:cooldown", 1, ex=settings.OTP_RESEND_COOLDOWN)
    return Challenge(cid, user.pk, purpose, code)


def get_challenge(cid: str) -> dict[str, str]:
    # redis-py types sync and asyncio clients together, so hgetall() is typed as
    # `dict | Awaitable[dict]`. Our client is sync with decode_responses=True.
    data = cast("dict[str, str]", get_redis().hgetall(_key(cid))) if cid else {}
    if not data:
        raise OTPError("This code has expired. Please request a new one.")
    return data


def resend(cid: str) -> Challenge:
    r = get_redis()
    data = get_challenge(cid)
    if r.exists(f"{_key(cid)}:cooldown"):
        raise OTPError(
            f"Please wait {r.ttl(f'{_key(cid)}:cooldown')}s before requesting another code."
        )
    code = _new_code()
    r.hset(_key(cid), mapping={"hash": _hash(cid, code), "attempts": 0})
    r.expire(_key(cid), settings.OTP_TTL_SECONDS)
    r.set(f"{_key(cid)}:cooldown", 1, ex=settings.OTP_RESEND_COOLDOWN)
    return Challenge(cid, int(data["user_id"]), data["purpose"], code)


def verify(cid: str, code: str, purpose: str) -> int:
    """Validate the code; returns the user id and consumes the challenge."""
    r = get_redis()
    data = get_challenge(cid)
    if data["purpose"] != purpose:
        raise OTPError("Invalid verification request.")
    attempts = r.hincrby(_key(cid), "attempts", 1)
    if attempts > settings.OTP_MAX_ATTEMPTS:
        r.delete(_key(cid))
        raise OTPError("Too many attempts. Please start again.")
    if not hmac.compare_digest(data["hash"], _hash(cid, (code or "").strip())):
        left = settings.OTP_MAX_ATTEMPTS - attempts
        if left <= 0:
            r.delete(_key(cid))
            raise OTPError("Too many attempts. Please start again.")
        raise OTPError(
            f"Incorrect code. {left} attempt{'s' if left != 1 else ''} left."
        )
    r.delete(_key(cid), f"{_key(cid)}:cooldown")
    return int(data["user_id"])
