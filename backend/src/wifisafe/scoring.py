"""공용 채점 공식 (plan.md §6.3). 순수 함수만 둔다.

[이 파일이 하는 일]
  rules.py가 구한 위험비율 8개(r1~r8)와 가중치 8개를 받아 0~100점 점수와 등급(낮음/주의/높음)을 계산합니다.
  '순수 함수'란 같은 입력을 넣으면 언제나 같은 결과를 내고, 파일·인터넷 등 바깥을 건드리지 않는 함수입니다.

[점수 공식]
  점수 = 100 × (켜 둔 요인들의 '가중치 × 위험비율' 합) ÷ (켜 둔 요인들의 가중치 합)
  예) R1(가중치 30, 비율 1.0)과 R2(가중치 20, 비율 0.5)만 켰다면
      100 × (30×1.0 + 20×0.5) ÷ (30+20) = 100 × 40 ÷ 50 = 80점 → '높음'

[왜 반올림을 직접 만들었나]
  Python·초안 JS·Next.js TS 세 곳이 같은 결과를 내야 하므로 반올림 방식을 명시적으로 고정한다:
    round2(x) = floor(x * 100 + 0.5 + 1e-9) / 100   (x ≥ 0, half-up)
  Python 내장 round()는 banker's rounding이라 JS Math.round와 다르므로 쓰지 않는다.
  (banker's rounding: 2.5 → 2처럼 '짝수 쪽'으로 반올림하는 방식. 일반적인 반올림(2.5 → 3)과 결과가 다를 수 있음)
  같은 계산이 frontend/src/lib/score.ts, web-draft/js/score.js에도 있고, contracts/golden_scores.json으로 세 곳 결과가 같은지 검사한다.

  이 모듈은 background 모듈을 import하지 않는다(범죄 통계 점수 반영 금지, test_isolation.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

# 점수를 낼 수 없을 때 돌려주는 오류 코드와 경고 코드. 화면에서 이 코드를 보고 안내 문구를 띄운다.
ERR_TOO_FEW_RULES = "TOO_FEW_RULES"   # 켜 둔 요인이 너무 적음(2개 미만)
ERR_ZERO_WEIGHT = "ZERO_WEIGHT"       # 켜 둔 요인의 가중치 합이 0
WARN_LOW_MAXSUM = "LOW_MAXSUM"        # 점수는 냈지만 가중치 합이 작아 근거가 빈약함


@dataclass(frozen=True)
class ScoreResult:
    """채점 결과 한 건. 오류가 나면 score·grade는 None이고 error에 코드가 들어간다."""
    score: float | None
    grade: str | None
    error: str | None = None
    warnings: tuple = field(default_factory=tuple)


def round2(x: float) -> float:
    """소수 둘째 자리까지 일반 반올림(0.5는 올림). 예) 12.345 → 12.35

    1e-9(아주 작은 수)를 더하는 이유: 컴퓨터는 12.345를 12.34499999…처럼 저장하기도 해서
    그대로 두면 내림이 되어 버리는 경우가 있기 때문이다.
    """
    return math.floor(x * 100 + 0.5 + 1e-9) / 100


def grade_for(score: float, grades: Sequence) -> str:
    """grades: (min, max, label, ...) 튜플 또는 {"min","max","label"} dict 시퀀스. min ≤ score < max.

    점수가 어느 등급 구간에 들어가는지 찾아 등급 이름을 돌려준다. 예) 45 → "주의"
    """
    for g in grades:
        lo, hi, label = (g["min"], g["max"], g["label"]) if isinstance(g, dict) else (g[0], g[1], g[2])
        if lo <= score < hi:
            return label
    raise ValueError(f"등급 구간에 속하지 않는 점수: {score}")


def compute_score(r: Sequence[float], weights: Sequence[float], selected: Sequence[bool],
                  grades: Sequence, params: dict) -> ScoreResult:
    """점수 계산의 본체.

    - r: 요인별 위험비율 8개 (0~1)
    - weights: 요인별 가중치 8개 (사용자가 슬라이더로 바꿀 수 있음)
    - selected: 요인별 켜짐/꺼짐 8개 (True=점수에 포함)
    - grades: 등급 구간표, params: config/rules.py의 PARAMS
    """
    if not (len(r) == len(weights) == len(selected)):
        raise ValueError("r, weights, selected 길이가 다름")
    idx = [i for i, s in enumerate(selected) if s]   # 켜 둔 요인의 순번만 모은다
    if len(idx) < params["MIN_SELECTED_RULES"]:
        return ScoreResult(None, None, ERR_TOO_FEW_RULES)
    wsum = sum(weights[i] for i in idx)              # 켜 둔 요인의 가중치 합 = 분모
    if wsum <= 0:
        return ScoreResult(None, None, ERR_ZERO_WEIGHT)
    warnings = (WARN_LOW_MAXSUM,) if wsum < params["LOW_MAXSUM_WARN"] else ()
    raw = 100 * sum(weights[i] * r[i] for i in idx) / wsum
    score = round2(raw)
    return ScoreResult(score, grade_for(score, grades), None, warnings)


def default_score(r: Sequence[float]) -> ScoreResult:
    """config/rules.py 기본 가중치·전체 선택 기준 점수.

    사용자가 아무것도 바꾸지 않았을 때(8개 요인 모두 켜고 기본 가중치)의 점수.
    """
    from config.rules import DEFAULT_WEIGHTS, GRADES, PARAMS
    return compute_score(r, DEFAULT_WEIGHTS, [True] * len(DEFAULT_WEIGHTS), GRADES, PARAMS)
