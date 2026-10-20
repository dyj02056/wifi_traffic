"""금지 표현·근거 외 수치·문장 수 검사 (plan.md §0-7, §8.4)."""
from __future__ import annotations

import re
from functools import lru_cache

from wifisafe.io import CONFIG_DIR, read_yaml

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+")


@lru_cache(maxsize=1)
def _kw() -> dict:
    return read_yaml(CONFIG_DIR / "keywords.yaml")


def forbidden_phrases() -> list[str]:
    return list(_kw().get("forbidden_phrases") or [])


def find_forbidden(text: str) -> list[str]:
    """허용된 부정형(면책 문구 등)을 지운 뒤 남은 금지 표현을 돌려준다."""
    t = text or ""
    for neg in sorted(_kw().get("allowed_negations") or [], key=len, reverse=True):
        t = t.replace(neg, " ")
    return [p for p in forbidden_phrases() if p in t]


def numbers_in(text: str) -> list[str]:
    return _NUM_RE.findall(text or "")


def allowed_numbers(values) -> set[float]:
    """입력 값(문자열·숫자 섞여도 됨)에서 등장하는 모든 수치 집합."""
    out: set[float] = set()
    for v in values:
        if v is None:
            continue
        if isinstance(v, (int, float)):
            out.add(round(float(v), 2))
            continue
        for n in numbers_in(str(v)):
            out.add(round(float(n), 2))
    return out


def unknown_numbers(text: str, allowed: set[float]) -> list[str]:
    return [n for n in numbers_in(text) if round(float(n), 2) not in allowed]


def sentence_count(text: str) -> int:
    parts = [p for p in _SENT_SPLIT.split((text or "").strip()) if p.strip()]
    return len(parts)


def check_explanation(text: str, allowed: set[float], min_sent: int = 2, max_sent: int = 3) -> list[str]:
    """실패 사유 목록(비면 통과)."""
    problems = []
    bad = find_forbidden(text)
    if bad:
        problems.append(f"금지 표현: {bad}")
    unk = unknown_numbers(text, allowed)
    if unk:
        problems.append(f"근거 외 수치: {unk}")
    n = sentence_count(text)
    if not (min_sent <= n <= max_sent):
        problems.append(f"문장 수 {n}개(허용 {min_sent}~{max_sent})")
    return problems
