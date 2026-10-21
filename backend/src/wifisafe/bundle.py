"""정적 번들(contracts/ 스키마) 조립. export_bundle.py와 make_mock.py가 같은 함수를 쓴다.

[이 파일이 하는 일]
  채점 결과를 화면(프론트엔드)이 읽을 JSON 파일들로 바꿉니다. 이 파일 묶음을 '번들'이라고 부릅니다.
  번들 구성 (각 파일의 모양은 contracts/schemas/에 정해져 있음):
    - meta.json        : 번들 전체 정보(버전, 데이터 기준일, 출처, 안내 문구)
    - rules.json       : 위험요인 8개 설명, 등급표, 채점 숫자, 수식
    - regions.json     : 시도·시군구 목록과 지역별 지도 범위
    - points/<지역>.json      : 지도에 찍을 지점 목록(좌표·위험비율·점수)
    - detail/<지역>.json      : 지점을 눌렀을 때 보여 줄 상세 정보(근거·설명·안전 수칙)
    - changes/<지역>.json     : 최근 추가·삭제된 지점
    - sensitivity/<지역>.json : 민감도 분석 결과
    - key_index.json   : 지점 고유키 → 어느 지역 파일에 있는지
    - background.json, cases.json : 배경 통계, 사례 카드 (점수 미반영)
  golden_json은 Python·JS·TS 채점 결과가 같은지 검사할 '정답표'(golden_scores.json)를 만듭니다.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from config.rules import DEFAULT_WEIGHTS, DISCLAIMER, GRADES, PARAMS, RULES, SENSITIVITY_B_OVERRIDES, RULE_IDS
from wifisafe import changes as CH
from wifisafe import sensitivity as SE
from wifisafe.geo import view_bbox
from wifisafe.io import contract_version, now_iso, write_json
from wifisafe.safety_tips import tips_for
from wifisafe.scoring import compute_score, round2

# 위험비율 칸 이름 목록: ["r1", "r2", ..., "r8"]
RCOLS = [f"r{i}" for i in range(1, 9)]
# 채점 수식을 글로 적은 것. rules.json에 실려 /rules 화면에 표시된다.
# (Σ는 '모두 더한다', S는 '켜 둔 요인들의 모음', w_i는 가중치, r_i는 위험비율)
FORMULA = {
    "score": "score = round2(100 × Σ_{i∈S}(w_i × r_i) / Σ_{i∈S} w_i)",
    "rounding": "round2(x) = floor(x × 100 + 0.5 + 1e-9) / 100  (Python round()·toFixed 사용 금지)",
    "grade": "grades에서 min ≤ score < max 인 항목 (반올림된 score로 판정)",
    "errors": "|S| < MIN_SELECTED_RULES → TOO_FEW_RULES (먼저 검사), Σ_{i∈S} w_i ≤ 0 → ZERO_WEIGHT; 둘 다 점수·등급 없음",
    "low_maxsum_basis": "Σ_{i∈S} w_i(현재 슬라이더 가중치) < LOW_MAXSUM_WARN 이면 LOW_MAXSUM 경고, 계산은 함",
}


def _s(v):
    """빈 문자열·NaN → None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    v = str(v).strip()
    return v or None


def rules_json() -> dict:
    """rules.json 내용: config/rules.py의 요인·등급·숫자를 그대로 JSON 모양으로 옮긴다."""
    return {
        "rules": [{"id": r.id, "name": r.name, "max_points": r.max_points, "is_assumption": r.is_assumption,
                   "source_fields": list(r.source_fields), "one_liner": r.one_liner} for r in RULES],
        "grades": [{"min": g[0], "max": g[1], "label": g[2], "emoji": g[3], "color": g[4]} for g in GRADES],
        "params": dict(PARAMS),
        "formula": FORMULA,
    }


def meta_json(*, is_mock: bool, r1_confirmed: bool, app_mode: str, data_reference_date, snapshot_collected_at,
              snapshot_count: int, regions_in_bundle: list[str], sources: list[dict]) -> dict:
    """meta.json 내용: 번들 전체에 대한 정보(가짜 데이터인지, 데이터 기준일, 만든 시각, 출처 등)."""
    return {
        "contract_version": contract_version(),
        "disclaimer": DISCLAIMER,
        "is_mock": is_mock,
        "r1_confirmed": r1_confirmed,
        "app_mode": app_mode,
        "data_reference_date": data_reference_date,
        "snapshot_collected_at": snapshot_collected_at,
        "snapshot_count": snapshot_count,
        "generated_at": now_iso(),
        "regions_in_bundle": regions_in_bundle,
        "sources": sources,
    }


def regions_json(clean: pd.DataFrame, available: set[str], default_region_id: str,
                 r1_status: dict[str, tuple[str, float | None]]) -> dict:
    """regions.json 내용: 시도 목록 + 시군구 목록(지점 수, 번들 포함 여부, SSID 확정 상태, 지도 중심·범위)."""
    regions = []
    for rid, g in clean.groupby("region_id", sort=True):
        st, cov = r1_status[rid]
        regions.append({
            "region_id": rid, "sido_code": rid[:2], "sido": g["sido"].iloc[0], "sigungu": g["sigungu"].iloc[0],
            "count": int(len(g)), "available": rid in available, "r1_status": st, "r1_coverage": cov,
            "center": {"lat": round(float(g["lat"].mean()), 6), "lng": round(float(g["lng"].mean()), 6)},
            "bbox": view_bbox(g["lat"], g["lng"]),   # 처음 화면 범위: 이상 좌표 빼고 중심부 (#32, #38)
        })
    sido = (clean.groupby(["sido_code", "sido"]).size().reset_index(name="count").sort_values("sido_code"))
    return {
        "default_region_id": default_region_id,
        "sido": [{"sido_code": a, "sido": b, "count": int(c)} for a, b, c in sido.itertuples(index=False)],
        "regions": regions,
    }


def _flags(v) -> list[str]:
    """"R1_unknown;R4_missing" 같은 글자를 ["R1_unknown", "R4_missing"] 목록으로 나눈다."""
    return [f for f in str(v or "").split(";") if f]


def points_json(region_id: str, scored: pd.DataFrame) -> dict:
    """points/<지역>.json 내용: 지도에 찍을 지점들. 화면이 직접 다시 채점할 수 있게 위험비율 r(8개)도 넣는다."""
    sub = scored[scored["region_id"] == region_id].sort_values("key")
    pts = [{
        "key": r["key"], "name": r["place_name"],
        "lat": round(float(r["lat"]), 6), "lng": round(float(r["lng"]), 6),
        "r": [float(r[c]) for c in RCOLS], "score": float(r["score"]), "grade": r["grade"],
        "flags": _flags(r["flags"]),
    } for _, r in sub.iterrows()]
    return {"region_id": region_id, "count": len(pts), "points": pts}


def detail_record(r) -> dict:
    """지점 한 곳의 상세 정보: 원본 근거(evidence), 요인별 점수 내역(breakdown), 안전 수칙, 신고 연락처."""
    breakdown = [{
        "id": rule.id, "name": rule.name, "ratio": float(r[f"r{i}"]),
        "points": round2(float(r[f"r{i}"]) * rule.max_points), "max_points": rule.max_points,
        "is_assumption": rule.is_assumption, "reason": str(r[f"reason{i}"]),
    } for i, rule in enumerate(RULES, start=1)]
    tips = tips_for(breakdown, r["grade"])
    return {
        "key": r["key"], "region_id": r["region_id"], "name": r["place_name"],
        "score": float(r["score"]), "grade": r["grade"],
        "evidence": {
            "ssid": _s(r["ssid"]), "facility_type": _s(r["facility_type"]), "place_detail": _s(r["place_detail"]),
            "install_ym": _s(r["install_ym_norm"]), "provider": _s(r["provider"]), "manager": _s(r["manager"]),
            "manager_tel": _s(r["manager_tel"]), "data_date": _s(r["data_date_norm"]), "address": _s(r["address"]),
            "open_ap_within_radius": int(r["open_ap_within_radius"]),
        },
        "breakdown": breakdown,
        "explanation": None,   # attach_explanations()에서 채움
        "safety_tips": tips,
        "report_contact": {"manager": _s(r["manager"]), "tel": _s(r["manager_tel"])},
        "flags": _flags(r["flags"]),
    }


def detail_json(region_id: str, scored: pd.DataFrame, explanations: dict | None = None) -> dict:
    """detail/<지역>.json 내용: 지점 고유키 → 상세 정보.

    자동 설명은 미리 만들어 둔 것(explanations)이 있으면 그것을, 없으면 템플릿 문장을 쓴다.
    """
    from wifisafe.explain import template_explanation
    sub = scored[scored["region_id"] == region_id].sort_values("key")
    out = {}
    for _, r in sub.iterrows():
        d = detail_record(r)
        pre = (explanations or {}).get(d["key"])
        d["explanation"] = pre if pre else template_explanation(d)
        out[d["key"]] = d
    return out


def sensitivity_json(region_id: str, scored: pd.DataFrame) -> dict:
    """sensitivity/<지역>.json 내용: 그 지역의 민감도 분석 결과 (계산은 sensitivity.py)."""
    sub = scored[scored["region_id"] == region_id]
    rows, summary = SE.analyze(sub)
    return SE.to_json(region_id, rows, summary)


def changes_json(region_id: str, changes: pd.DataFrame, snapshots: list[str]) -> dict:
    """changes/<지역>.json 내용: 그 지역에서 최근 추가·삭제된 지점 (계산은 changes.py)."""
    return CH.to_json(region_id, changes, snapshots)


# ── golden ─────────────────────────────────────────────────────
# golden = '정답표'. 여러 입력에 대해 Python이 계산한 점수를 적어 두고,
# JS·TS 채점 코드가 같은 입력에서 같은 답을 내는지 테스트로 확인한다.
def _case(cid: str, r, weights, selected) -> dict:
    """정답표 한 줄: 입력(r, weights, selected)과 Python이 계산한 기대 결과."""
    res = compute_score(list(r), list(weights), list(selected), GRADES, PARAMS)
    return {"id": cid, "r": [float(x) for x in r], "weights": [float(w) for w in weights],
            "selected": [bool(s) for s in selected], "expected_score": res.score, "expected_grade": res.grade,
            "expected_error": res.error, "expected_warnings": list(res.warnings)}


def golden_json(sample_r: list[list[float]], generated_from: str) -> dict:
    """golden_scores.json 내용. 손으로 고른 경계 사례 + 실제 지점 표본(기본 가중치·무작위 가중치)으로 구성."""
    W = list(DEFAULT_WEIGHTS)
    ALL = [True] * 8
    WB = [SENSITIVITY_B_OVERRIDES.get(rid, w) for rid, w in zip(RULE_IDS, W)]
    ex = [1, 1, 1, 0.75, 0.4, 0, 0, 0]   # plan.md에 나오는 예시 지점의 위험비율
    z = [0.0] * 8
    # 일부러 까다로운 경우를 모았다: 등급 경계(29.99/30, 59.99/60), 반올림, 일부 요인만 켜기, 오류 상황 등
    cases = [
        _case("plan-example-default", ex, W, ALL),
        _case("plan-example-r1-15", ex, WB, ALL),
        _case("all-zero", z, W, ALL),
        _case("all-one", [1] * 8, W, ALL),
        _case("boundary-29.99", [0.9997, 0, 0, 0, 0, 0, 0, 0], W, ALL),
        _case("boundary-30", [1, 0, 0, 0, 0, 0, 0, 0], W, ALL),
        _case("boundary-59.99", [1, 1, 0, 0.666, 0, 0, 0, 0], W, ALL),
        _case("boundary-60", [1, 1, 1, 0, 0, 0, 0, 0], W, ALL),
        _case("half-up-rounding", [0.33333, 0.5, 0.125, 0.0625, 0.2, 0.7, 0.1, 0.9], W, ALL),
        _case("partial-r1-r5", ex, W, [True, False, False, False, True, False, False, False]),
        _case("partial-r1-r2-r3", [1, 0.5, 0, 0, 0, 0, 0, 0], W, [True, True, True, False, False, False, False, False]),
        _case("partial-low-maxsum-warn", [1, 1, 1, 1, 1, 1, 1, 0], W,
              [False, False, False, False, False, True, True, True]),
        _case("partial-maxsum-exactly-30", [0, 0, 1, 1, 0, 1, 0, 0], [30, 20, 10, 15, 10, 5, 5, 5],
              [False, False, True, True, False, True, False, False]),
        _case("too-few-one-selected", ex, W, [True, False, False, False, False, False, False, False]),
        _case("too-few-none-selected", ex, W, [False] * 8),
        _case("zero-weight-all", ex, [0] * 8, ALL),
        _case("zero-weight-selected", ex, [0, 0, 10, 15, 10, 5, 5, 5],
              [True, True, False, False, False, False, False, False]),
        _case("one-weight-zero", ex, [0, 20, 10, 15, 10, 5, 5, 5], ALL),
        _case("double-weights", ex, [w * 2 for w in W], ALL),
        _case("fractional-weights", [0.2, 0.4, 0.6, 0.8, 1, 0.5, 0.25, 0.75], [7.5, 12.5, 3, 22, 1.5, 9, 0.5, 18], ALL),
        _case("r1-only-max-r2", [0, 1, 0, 0, 0, 0, 0, 0], [0, 40, 0, 0, 0, 0, 0, 0],
              [True, True, False, False, False, False, False, False]),
    ]
    # 무작위 값이지만 시작 번호(seed)를 고정해서 매번 똑같은 '무작위' 사례가 나오게 한다.
    rng = random.Random(20261020)
    for i, r in enumerate(sample_r[:15]):
        cases.append(_case(f"{generated_from}-sample-{i}-default", r, W, ALL))
        rw = [rng.choice([0, 1, 2.5, 5, 10, 15, 20, 30, 45, 60]) for _ in range(8)]
        rs = [rng.random() < 0.7 for _ in range(8)]
        cases.append(_case(f"{generated_from}-sample-{i}-random", r, rw, rs))
    return {
        "generated_at": now_iso(),
        "generated_from": generated_from,
        "tolerance": 0.01,
        "formula": FORMULA,
        "grades": rules_json()["grades"],
        "params": {"MIN_SELECTED_RULES": PARAMS["MIN_SELECTED_RULES"], "LOW_MAXSUM_WARN": PARAMS["LOW_MAXSUM_WARN"]},
        "cases": cases,
    }


# 이 폴더의 파일은 용량이 커서 줄바꿈·들여쓰기 없이 한 줄로 압축해 저장한다.
COMPACT_FOLDERS = ("points", "detail")


def bundle_docs(*, meta: dict, regions: dict, scored: pd.DataFrame, region_ids: list[str],
                changes: pd.DataFrame, snapshots: list[str], background: dict, cases: dict,
                explanations: dict | None = None):
    """번들 문서를 (상대경로, JSON) 순서대로 낸다. 파일(write_bundle)·DB(db.put_docs) 저장이 같은 문서를 쓴다.
    지역 수가 많아도 메모리에 전부 올리지 않도록 generator로 만든다.

    (generator: yield로 결과를 하나씩 내보내는 함수. 전부 만들어 쌓아 두지 않고 필요할 때 하나씩 만든다.)
    """
    yield "meta.json", meta
    yield "rules.json", rules_json()
    yield "regions.json", regions
    key_index = {}
    for rid in region_ids:
        pj = points_json(rid, scored)
        yield f"points/{rid}.json", pj
        yield f"detail/{rid}.json", detail_json(rid, scored, (explanations or {}).get(rid))
        yield f"changes/{rid}.json", changes_json(rid, changes, snapshots)
        yield f"sensitivity/{rid}.json", sensitivity_json(rid, scored)
        for p in pj["points"]:
            key_index[p["key"]] = rid
    yield "key_index.json", key_index
    yield "background.json", background
    yield "cases.json", cases


def write_bundle(out_dir: Path, **kwargs) -> None:
    """번들 문서를 out_dir 폴더에 JSON 파일로 저장한다."""
    for rel, doc in bundle_docs(**kwargs):
        write_json(out_dir / rel, doc, compact=rel.split("/")[0] in COMPACT_FOLDERS)
