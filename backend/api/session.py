"""세션 토큰: base64url(JSON{uid, exp}).HMAC-SHA256 — 서버에 세션 저장소가 없어도 된다(서버리스).

[이 파일이 하는 일]
  로그인한 사용자에게 '출입증(토큰)'을 발급하고, 다음 요청 때 그 출입증이 진짜인지 확인합니다.
  토큰 모양: "<내용>.<서명>"
    - 내용: {"uid": 회원번호, "exp": 만료 시각}을 base64url(글자로 안전하게 바꾸는 방식)로 바꾼 것
    - 서명: 서버만 아는 비밀값(SESSION_SECRET)으로 내용에 찍은 도장(HMAC-SHA256)
  누군가 내용을 고치면 서명이 맞지 않게 되므로 위조를 알아챌 수 있습니다.
  이 방식이면 서버가 '누가 로그인했는지' 따로 저장해 둘 필요가 없습니다.

비밀값은 환경변수 SESSION_SECRET에서만 읽는다(없으면 회원 기능 비활성).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

# 토큰 유효 기간: 30일(초 단위)
TTL_SECONDS = 30 * 24 * 3600


def _secret() -> bytes:
    """서명용 비밀값을 읽는다. 16자 미만이면 너무 약하므로 오류."""
    s = os.environ.get("SESSION_SECRET", "")
    if len(s) < 16:
        raise RuntimeError("SESSION_SECRET(16자 이상)이 없습니다")
    return s.encode()


def _b64(b: bytes) -> str:
    """바이트 → base64url 글자 (끝의 '=' 채움 문자는 뗀다)."""
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    """base64url 글자 → 바이트 (뗐던 '='를 길이에 맞게 다시 붙여서 해석)."""
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue(user_id: int, now: float | None = None) -> str:
    """회원번호로 새 토큰을 만든다."""
    body = _b64(json.dumps({"uid": user_id, "exp": int((now or time.time()) + TTL_SECONDS)}).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(token: str, now: float | None = None) -> int | None:
    """올바른 토큰이면 user id, 아니면 None.

    서명이 맞지 않거나(위조), 만료됐거나, 모양이 이상하면 None.
    compare_digest는 비교 시간으로 정답을 추측하는 공격을 막는 안전한 비교 함수다.
    """
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
