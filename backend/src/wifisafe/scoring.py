"""공용 채점 공식 (plan.md §6.3). 순수 함수만 둔다.

Python·초안 JS·Next.js TS 세 곳이 같은 결과를 내야 하므로 반올림 방식을 명시적으로 고정한다:
  round2(x) = floor(x * 100 + 0.5 + 1e-9) / 100   (x ≥ 0, half-up)
Python 내장 round()는 banker's rounding이라 JS Math.round와 다르므로 쓰지 않는다.

이 모듈은 background 모듈을 import하지 않는다(범죄 통계 점수 반영 금지, test_isolation.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

ERR_TOO_FEW_RULES = "TOO_FEW_RULES"
ERR_ZERO_WEIGHT = "ZERO_WEIGHT"
WARN_LOW_MAXSUM = "LOW_MAXSUM"


@dataclass(frozen=True)
class ScoreResult:
    score: float | None
    grade: str | None
    error: str | None = None
    warnings: tuple = field(default_factory=tuple)


def round2(x: float) -> float:
    return math.floor(x * 100 + 0.5 + 1e-9) / 100


def grade_for(score: float, grades: Sequence) -> str:
    """grades: (min, max, label, ...) 튜플 또는 {"min","max","label"} dict 시퀀스. min ≤ score < max."""
    for g in grades:
        lo, hi, label = (g["min"], g["max"], g["label"]) if isinstance(g, dict) else (g[0], g[1], g[2])
        if lo <= score < hi:
            return label
    raise ValueError(f"등급 구간에 속하지 않는 점수: {score}")


def compute_score(r: Sequence[float], weights: Sequence[float], selected: Sequence[bool],
                  grades: Sequence, params: dict) -> ScoreResult:
    if not (len(r) == len(weights) == len(selected)):
        raise ValueError("r, weights, selected 길이가 다름")
    idx = [i for i, s in enumerate(selected) if s]
    if len(idx) < params["MIN_SELECTED_RULES"]:
        return ScoreResult(None, None, ERR_TOO_FEW_RULES)
    wsum = sum(weights[i] for i in idx)
    if wsum <= 0:
        return ScoreResult(None, None, ERR_ZERO_WEIGHT)
    warnings = (WARN_LOW_MAXSUM,) if wsum < params["LOW_MAXSUM_WARN"] else ()
    raw = 100 * sum(weights[i] * r[i] for i in idx) / wsum
    score = round2(raw)
    return ScoreResult(score, grade_for(score, grades), None, warnings)


def default_score(r: Sequence[float]) -> ScoreResult:
    """config/rules.py 기본 가중치·전체 선택 기준 점수."""
    from config.rules import DEFAULT_WEIGHTS, GRADES, PARAMS
    return compute_score(r, DEFAULT_WEIGHTS, [True] * len(DEFAULT_WEIGHTS), GRADES, PARAMS)
