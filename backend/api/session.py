"""세션 토큰: base64url(JSON{uid, exp}).HMAC-SHA256 — 서버에 세션 저장소가 없어도 된다(서버리스).

비밀값은 환경변수 SESSION_SECRET에서만 읽는다(없으면 회원 기능 비활성).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

TTL_SECONDS = 30 * 24 * 3600


def _secret() -> bytes:
    s = os.environ.get("SESSION_SECRET", "")
    if len(s) < 16:
        raise RuntimeError("SESSION_SECRET(16자 이상)이 없습니다")
    return s.encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue(user_id: int, now: float | None = None) -> str:
    body = _b64(json.dumps({"uid": user_id, "exp": int((now or time.time()) + TTL_SECONDS)}).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(token: str, now: float | None = None) -> int | None:
    """올바른 토큰이면 user id, 아니면 None."""
    try:
        body, sig = token.split(".")
        expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(body))
        if data["exp"] < (now or time.time()):
            return None
        return int(data["uid"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
