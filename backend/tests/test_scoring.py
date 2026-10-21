# [이 테스트가 확인하는 것]
#   점수 공식(wifisafe/scoring.py)을 확인한다: plan.md 예시 계산, 반올림, 등급 경계(30·60점),
#   요인을 너무 적게 켰거나 가중치 합이 0일 때의 오류, 그리고 golden_scores.json 정답표와 일치하는지.
import json

import pytest

from config.rules import DEFAULT_WEIGHTS, GRADES, PARAMS
from wifisafe.io import GOLDEN_PATH
from wifisafe.scoring import ERR_TOO_FEW_RULES, ERR_ZERO_WEIGHT, WARN_LOW_MAXSUM, compute_score, grade_for, round2

ALL = [True] * 8


def test_plan_example_75_25():
    r = [1, 1, 1, 0.75, 0.4, 0, 0, 0]
    res = compute_score(r, DEFAULT_WEIGHTS, ALL, GRADES, PARAMS)
    assert res.score == 75.25 and res.grade == "높음"


def test_default_total_equals_sum_max_times_r():
    r = [0.3, 0.6, 1, 0.2, 0.8, 0.5, 1, 0]
    expected = round2(sum(w * x for w, x in zip(DEFAULT_WEIGHTS, r)))   # 만점 합 100
    assert sum(DEFAULT_WEIGHTS) == 100
    assert compute_score(r, DEFAULT_WEIGHTS, ALL, GRADES, PARAMS).score == expected


def test_too_few_rules():
    sel = [True] + [False] * 7
    res = compute_score([1] * 8, DEFAULT_WEIGHTS, sel, GRADES, PARAMS)
    assert res.error == ERR_TOO_FEW_RULES and res.score is None


def test_zero_weight():
    res = compute_score([1] * 8, [0] * 8, ALL, GRADES, PARAMS)
    assert res.error == ERR_ZERO_WEIGHT and res.score is None


def test_low_maxsum_warning_still_computes():
    sel = [False] * 5 + [True, True, True]          # 5+5+5 = 15 < 30
    res = compute_score([0, 0, 0, 0, 0, 1, 1, 0], DEFAULT_WEIGHTS, sel, GRADES, PARAMS)
    assert WARN_LOW_MAXSUM in res.warnings and res.score == 66.67


@pytest.mark.parametrize("score,grade", [(0, "낮음"), (29.99, "낮음"), (30, "주의"), (59.99, "주의"),
                                         (60, "높음"), (100, "높음")])
def test_grade_boundaries(score, grade):
    assert grade_for(score, GRADES) == grade


def test_round2_half_up():
    assert round2(0.125) == 0.13       # Python round(0.125, 2) == 0.12 (banker's)
    assert round2(75.25) == 75.25
    assert round2(29.991) == 29.99


def test_golden_file_consistent():
    g = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert len(g["cases"]) >= 30
    ids = {c["id"] for c in g["cases"]}
    assert {"boundary-29.99", "boundary-30", "boundary-59.99", "boundary-60", "zero-weight-all",
            "too-few-one-selected"} <= ids
    for c in g["cases"]:
        res = compute_score(c["r"], c["weights"], c["selected"], GRADES, PARAMS)
        assert res.score == c["expected_score"], c["id"]
        assert res.grade == c["expected_grade"], c["id"]
        assert res.error == c["expected_error"], c["id"]
        assert list(res.warnings) == c["expected_warnings"], c["id"]
