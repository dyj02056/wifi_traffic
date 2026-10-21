"""민감도 분석: 기준 A(기본) vs 기준 B(R1=15) (plan.md §8.6).

[이 파일이 하는 일]
  "채점 기준을 조금만 바꿔도 결과가 크게 달라지는가?"를 확인합니다.
  기준 A(기본 가중치)와 기준 B(R1 가중치만 30 → 15)로 같은 지역 지점들을 각각 채점해 비교합니다.
  비교 항목:
    - top_overlap: 두 기준의 상위 20곳 중 겹치는 곳 수 (많을수록 결과가 안정적)
    - spearman: 두 순위가 얼마나 비슷한지 (1에 가까울수록 순위가 거의 같음)
    - grade_moves: 등급이 바뀐 지점 수
  (/sensitivity 화면의 8개 기준 × 끄기/2배 분석은 브라우저에서 따로 계산한다.)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.rules import DEFAULT_WEIGHTS, GRADES, PARAMS, RULE_IDS, SENSITIVITY_B_OVERRIDES, SENSITIVITY_TOP_N
from wifisafe.scoring import compute_score

RCOLS = [f"r{i}" for i in range(1, 9)]


def weights_b() -> list[float]:
    """기준 B 가중치: 기본 가중치에서 SENSITIVITY_B_OVERRIDES에 적힌 것만 바꾼다. → [15, 20, 10, 15, 10, 5, 5, 5]"""
    return [SENSITIVITY_B_OVERRIDES.get(rid, w) for rid, w in zip(RULE_IDS, DEFAULT_WEIGHTS)]


def _scores(df: pd.DataFrame, weights) -> list:
    """표의 모든 지점을 주어진 가중치(8개 모두 켬)로 채점한다."""
    sel = [True] * len(weights)
    return [compute_score(list(v), weights, sel, GRADES, PARAMS) for v in df[RCOLS].to_numpy()]


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    """두 순위 목록의 상관계수(-1~1). 지점이 2개 미만이거나 값이 모두 같으면 계산할 수 없어 None."""
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def analyze(df: pd.DataFrame, top_n: int = SENSITIVITY_TOP_N) -> tuple[pd.DataFrame, dict]:
    """df: key, place_name, r1..r8. 순위는 점수 내림차순, 동점은 key 오름차순(결정적).

    ('결정적' = 몇 번을 돌려도 순위가 똑같이 나온다는 뜻. 동점을 key 순서로 정리하기 때문)
    돌려주는 값: (지점별 비교표, 요약 숫자)
    """
    wa, wb = list(DEFAULT_WEIGHTS), weights_b()
    sa, sb = _scores(df, wa), _scores(df, wb)
    out = pd.DataFrame({
        "key": df["key"].to_numpy(), "place_name": df["place_name"].to_numpy(),
        "score_A": [s.score for s in sa], "score_B": [s.score for s in sb],
        "grade_A": [s.grade for s in sa], "grade_B": [s.grade for s in sb],
    })
    # 기준별 순위 매기기: 점수 높은 순으로 줄 세워 1, 2, 3 … 번호를 붙인다.
    for col, rank in (("score_A", "rank_A"), ("score_B", "rank_B")):
        order = out.sort_values([col, "key"], ascending=[False, True]).index
        out.loc[order, rank] = np.arange(1, len(out) + 1)
    out["rank_A"] = out["rank_A"].astype(int)
    out["rank_B"] = out["rank_B"].astype(int)
    out["delta"] = out["rank_A"] - out["rank_B"]   # 양수면 기준 B에서 순위가 올라감
    out = out.sort_values("rank_A").reset_index(drop=True)
    n = min(top_n, len(out))
    top_a = set(out.nsmallest(n, "rank_A")["key"])
    top_b = set(out.nsmallest(n, "rank_B")["key"])
    # 스피어만 = 순위의 피어슨 상관 (동점은 key로 깨진 순위 사용)
    summary = {
        "count": int(len(out)),
        "top_n": int(max(n, 1)),
        "top_overlap": int(len(top_a & top_b)),   # & = 두 집합에 모두 있는 것
        "spearman": _spearman(out["rank_A"].to_numpy(float), out["rank_B"].to_numpy(float)),
        "grade_moves": int((out["grade_A"] != out["grade_B"]).sum()),
    }
    if summary["spearman"] is not None:
        summary["spearman"] = round(summary["spearman"], 4)
    cols = ["key", "place_name", "rank_A", "rank_B", "delta", "score_A", "score_B", "grade_A", "grade_B"]
    return out[cols], summary


def to_json(region_id: str, rows: pd.DataFrame, summary: dict) -> dict:
    """분석 결과를 sensitivity/<지역>.json 모양으로 만든다."""
    return {
        "region_id": region_id,
        "scenario_a": {"label": "기준 A(기본 가중치)", "weights": list(DEFAULT_WEIGHTS)},
        "scenario_b": {"label": "기준 B(" + ", ".join(f"{k}={v}" for k, v in SENSITIVITY_B_OVERRIDES.items()) + ")",
                       "weights": weights_b()},
        "summary": summary,
        "rows": [{**r, "place_name": r["place_name"] or None} for r in rows.to_dict(orient="records")],
    }
