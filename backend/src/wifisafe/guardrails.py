"""금지 표현·근거 외 수치·문장 수 검사 (plan.md §0-7, §8.4).

[이 파일이 하는 일]
  AI가 쓴 설명문(explain.py)이 안전한지 세 가지를 검사하는 '안전장치(가드레일)'입니다.
    1) 금지 표현: '해킹 확률', '위험 지역'처럼 오해를 부르는 말이 있는지 (목록은 config/keywords.yaml)
    2) 근거 외 수치: 우리가 준 자료에 없는 숫자를 AI가 지어냈는지
    3) 문장 수: 2~3문장인지
  하나라도 걸리면 그 AI 설명은 버리고 템플릿 문장을 대신 씁니다.
  scripts/check_disclaimer.py도 이 파일의 금지 표현 검사를 써서 화면 문구를 점검합니다.
"""
from __future__ import annotations

import re
from functools import lru_cache

from wifisafe.io import CONFIG_DIR, read_yaml

# 숫자(정수 또는 소수)를 찾는 패턴
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
# 문장 나누기: 마침표·느낌표·물음표 뒤의 공백에서 자른다
_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+")


@lru_cache(maxsize=1)
def _kw() -> dict:
    """keywords.yaml을 읽는다. lru_cache 덕분에 처음 한 번만 읽고 이후에는 기억해 둔 값을 쓴다."""
    return read_yaml(CONFIG_DIR / "keywords.yaml")


def forbidden_phrases() -> list[str]:
    """금지 표현 목록."""
    return list(_kw().get("forbidden_phrases") or [])


def find_forbidden(text: str) -> list[str]:
    """허용된 부정형(면책 문구 등)을 지운 뒤 남은 금지 표현을 돌려준다.

    예) "이 점수는 실제 해킹 확률이 아니라 …"의 '해킹 확률이 아니라'는 부정하는 말이므로 허용.
    긴 허용 표현부터 지워야 짧은 표현에 먼저 걸려 일부만 지워지는 일이 없다.
    """
    t = text or ""
    for neg in sorted(_kw().get("allowed_negations") or [], key=len, reverse=True):
        t = t.replace(neg, " ")
    return [p for p in forbidden_phrases() if p in t]


def numbers_in(text: str) -> list[str]:
    """글 속의 숫자를 모두 찾는다. 예) "약 6.2년, 5개" → ["6.2", "5"]"""
    return _NUM_RE.findall(text or "")


def allowed_numbers(values) -> set[float]:
    """입력 값(문자열·숫자 섞여도 됨)에서 등장하는 모든 수치 집합.

    소수 둘째 자리로 맞춰서 저장해 72.5와 72.50을 같은 숫자로 본다.
    """
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
    """글 속 숫자 중 허용 목록에 없는 것(= 지어낸 숫자로 의심되는 것)."""
    return [n for n in numbers_in(text) if round(float(n), 2) not in allowed]


def sentence_count(text: str) -> int:
    """문장 수를 센다."""
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
