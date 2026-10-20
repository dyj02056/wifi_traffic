"""민감도 분석: 기준 A(기본) vs 기준 B(R1=15) (plan.md §8.6)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.rules import DEFAULT_WEIGHTS, GRADES, PARAMS, RULE_IDS, SENSITIVITY_B_OVERRIDES, SENSITIVITY_TOP_N
from wifisafe.scoring import compute_score

RCOLS = [f"r{i}" for i in range(1, 9)]


def weights_b() -> list[float]:
    return [SENSITIVITY_B_OVERRIDES.get(rid, w) for rid, w in zip(RULE_IDS, DEFAULT_WEIGHTS)]


def _scores(df: pd.DataFrame, weights) -> list:
    sel = [True] * len(weights)
    return [compute_score(list(v), weights, sel, GRADES, PARAMS) for v in df[RCOLS].to_numpy()]


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def analyze(df: pd.DataFrame, top_n: int = SENSITIVITY_TOP_N) -> tuple[pd.DataFrame, dict]:
    """df: key, place_name, r1..r8. 순위는 점수 내림차순, 동점은 key 오름차순(결정적)."""
    wa, wb = list(DEFAULT_WEIGHTS), weights_b()
    sa, sb = _scores(df, wa), _scores(df, wb)
    out = pd.DataFrame({
        "key": df["key"].to_numpy(), "place_name": df["place_name"].to_numpy(),
        "score_A": [s.score for s in sa], "score_B": [s.score for s in sb],
        "grade_A": [s.grade for s in sa], "grade_B": [s.grade for s in sb],
    })
    for col, rank in (("score_A", "rank_A"), ("score_B", "rank_B")):
        order = out.sort_values([col, "key"], ascending=[False, True]).index
        out.loc[order, rank] = np.arange(1, len(out) + 1)
    out["rank_A"] = out["rank_A"].astype(int)
    out["rank_B"] = out["rank_B"].astype(int)
    out["delta"] = out["rank_A"] - out["rank_B"]
    out = out.sort_values("rank_A").reset_index(drop=True)
    n = min(top_n, len(out))
    top_a = set(out.nsmallest(n, "rank_A")["key"])
    top_b = set(out.nsmallest(n, "rank_B")["key"])
    # 스피어만 = 순위의 피어슨 상관 (동점은 key로 깨진 순위 사용)
    summary = {
        "count": int(len(out)),
        "top_n": int(max(n, 1)),
        "top_overlap": int(len(top_a & top_b)),
        "spearman": _spearman(out["rank_A"].to_numpy(float), out["rank_B"].to_numpy(float)),
        "grade_moves": int((out["grade_A"] != out["grade_B"]).sum()),
    }
    if summary["spearman"] is not None:
        summary["spearman"] = round(summary["spearman"], 4)
    cols = ["key", "place_name", "rank_A", "rank_B", "delta", "score_A", "score_B", "grade_A", "grade_B"]
    return out[cols], summary


def to_json(region_id: str, rows: pd.DataFrame, summary: dict) -> dict:
    return {
        "region_id": region_id,
        "scenario_a": {"label": "기준 A(기본 가중치)", "weights": list(DEFAULT_WEIGHTS)},
        "scenario_b": {"label": "기준 B(" + ", ".join(f"{k}={v}" for k, v in SENSITIVITY_B_OVERRIDES.items()) + ")",
                       "weights": weights_b()},
        "summary": summary,
        "rows": [{**r, "place_name": r["place_name"] or None} for r in rows.to_dict(orient="records")],
    }
