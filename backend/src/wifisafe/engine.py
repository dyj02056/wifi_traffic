"""정제(clean)·채점(score) 공통 로직. pipeline/ 스크립트와 mock 생성기가 같은 코드를 쓴다."""
from __future__ import annotations

import warnings

import pandas as pd

from config.rules import DEFAULT_WEIGHTS, GRADES, PARAMS, RULE_IDS
from wifisafe import rules as R
from wifisafe.density import r5_density
from wifisafe.io import CONFIG_DIR, read_config_csv, read_yaml
from wifisafe.schema import (COLUMN_MAP, ID_COLUMN, MOCK_SIDO_CODE, PENDING_SIDO, REQUIRED_INTERNAL, point_key, sido_code,
                             sigungu_slug, validate_header)
from wifisafe.scoring import compute_score

KOREA_BBOX = (33.0, 39.5, 124.0, 132.0)   # lat_min, lat_max, lng_min, lng_max
VALID_LABELS = {"open", "secure", "unknown"}


# ── 사람이 확정한 표 읽기 + R1 게이트 ─────────────────────────────
def load_tables():
    """config/ 파일에서 RuleTables를 만든다. 반환: (tables, status dict)."""
    labels = read_config_csv("ssid_labels.csv")
    bad = sorted(set(labels["label"]) - VALID_LABELS)
    if bad:
        raise SystemExit(f"ssid_labels.csv에 허용되지 않는 label 값: {bad} (open|secure|unknown)")
    dup = labels["ssid"][labels["ssid"].duplicated()].tolist()
    if dup:
        raise SystemExit(f"ssid_labels.csv에 중복 SSID: {dup[:10]}")
    fac = read_config_csv("facility_map.csv")
    fac_map = {}
    for _, row in fac.iterrows():
        ratio = float(row["ratio"])
        if not 0 <= ratio <= 1:
            raise SystemExit(f"facility_map.csv ratio는 0~1: {row['facility_type']}={ratio}")
        fac_map[row["facility_type"].strip()] = (ratio, row["reason"].strip())
    kw = read_yaml(CONFIG_DIR / "keywords.yaml")
    tables = R.RuleTables(
        ssid_labels=dict(zip(labels["ssid"], labels["label"])),
        facility_map=fac_map,
        outdoor_keywords=tuple(kw.get("r3_outdoor_keywords") or ()),
        indoor_override_keywords=tuple(kw.get("r3_indoor_override_keywords") or ()),
    )
    status = {
        "r1_confirmed": len(labels) > 0 and bool((labels["status"] == "confirmed").all()),
        "ssid_labels_total": int(len(labels)),
        "ssid_labels_confirmed": int((labels["status"] == "confirmed").sum()),
        "facility_map_total": int(len(fac)),
        "r3_status": kw.get("r3_status", "draft"),
    }
    return tables, status


def confirmed_ssids() -> set[str]:
    labels = read_config_csv("ssid_labels.csv")
    return set(labels.loc[labels["status"] == "confirmed", "ssid"])


def r1_region_status(df: pd.DataFrame, confirmed: set[str]) -> dict[str, tuple[str, float | None]]:
    """지역별 R1 확정 상태 (requests #23·#24). region_id → (status, coverage).

    coverage = SSID 있는 행 중 확정 라벨이 붙은 행 비율. 기준(R1_REGION_COVERAGE_MIN) 이상이면 confirmed,
    미만이면 provisional('임시(무효)'). SSID가 전부 빈 지역은 확정할 이름이 없으므로 no_ssid(coverage=None).
    """
    has = df["ssid"].fillna("").astype(str).str.strip().ne("")
    ok = df["ssid"].isin(confirmed) & has
    out = {}
    for rid, idx in df.groupby("region_id").groups.items():
        n = int(has.loc[idx].sum())
        if n == 0:
            out[rid] = ("no_ssid", None)
            continue
        cov = round(float(ok.loc[idx].sum()) / n, 4)
        out[rid] = ("confirmed" if cov >= PARAMS["R1_REGION_COVERAGE_MIN"] else "provisional", cov)
    return out


def enforce_r1_region_gate(mode: str, region_status: dict, region_ids: list[str]) -> None:
    if mode != "final":
        return
    bad = [f"{r}({region_status[r][1]:.1%})" for r in region_ids if region_status[r][0] == "provisional"]
    if bad:
        raise SystemExit(f"APP_MODE=final 이지만 SSID 라벨 확정 비율이 {PARAMS['R1_REGION_COVERAGE_MIN']:.0%} 미만인 지역이 "
                         f"번들에 있습니다: {bad} — 최종 번들 생성 중단")


def enforce_r1_gate(mode: str, status: dict) -> None:
    if mode == "final" and not status["r1_confirmed"]:
        raise SystemExit("APP_MODE=final 이지만 config/ssid_labels.csv가 전부 status=confirmed가 아닙니다. "
                         f"(확정 {status['ssid_labels_confirmed']}/{status['ssid_labels_total']}) — 최종 번들 생성 중단")


# ── clean ──────────────────────────────────────────────────────
def _norm_ym(v: str) -> str | None:
    ts, year_only = R.parse_install_ym(v)
    if ts is None:
        return None
    return f"{ts.year:04d}" if year_only else f"{ts.year:04d}-{ts.month:02d}"


def _norm_date(v: str) -> str | None:
    d = pd.to_datetime(v or None, errors="coerce", format="mixed")
    return None if pd.isna(d) else d.strftime("%Y-%m-%d")


def clean_frame(raw: pd.DataFrame, mock: bool = False) -> tuple[pd.DataFrame, dict]:
    validate_header(raw.columns)
    keep = list(COLUMN_MAP) + ([ID_COLUMN] if ID_COLUMN else [])
    df = raw[keep].rename(columns=COLUMN_MAP).copy()
    if ID_COLUMN:
        df = df.rename(columns={ID_COLUMN: "raw_id"})
    for c in df.columns:
        df[c] = df[c].fillna("").astype(str).str.strip()
    report = {"rows_in": int(len(df))}

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    swapped = df["lat"].between(124, 132) & df["lng"].between(33, 39.5)
    df.loc[swapped, ["lat", "lng"]] = df.loc[swapped, ["lng", "lat"]].to_numpy()
    report["coords_swapped_fixed"] = int(swapped.sum())
    lat0, lat1, lng0, lng1 = KOREA_BBOX
    bad_xy = ~(df["lat"].between(lat0, lat1) & df["lng"].between(lng0, lng1))
    report["dropped_bad_coords"] = int(bad_xy.sum())
    df = df[~bad_xy]
    missing_req = pd.Series(False, index=df.index)
    for c in ("place_name", "sido", "sigungu"):
        missing_req |= df[c].eq("")
    report["dropped_missing_required"] = int(missing_req.sum())
    df = df[~missing_req].copy()
    pending = df["sido"].isin(PENDING_SIDO) if not mock else pd.Series(False, index=df.index)
    report["excluded_pending_sido"] = {k: int(v) for k, v in df.loc[pending, "sido"].value_counts().items()}
    if report["excluded_pending_sido"]:
        warnings.warn(f"시도코드 확인 전이라 제외: {report['excluded_pending_sido']} (schema.py PENDING_SIDO)", stacklevel=2)
    df = df[~pending].copy()
    assert all(c in df.columns for c in REQUIRED_INTERNAL)

    # region_id
    pairs = df[["sido", "sigungu"]].drop_duplicates().sort_values(["sido", "sigungu"])
    region_of, used = {}, set()
    for sido, sgg in pairs.itertuples(index=False):
        base = f"{MOCK_SIDO_CODE if mock else sido_code(sido)}-{sigungu_slug(sgg)}"
        rid, n = base, 2
        while rid in used:
            rid, n = f"{base}-{n}", n + 1
        used.add(rid)
        region_of[(sido, sgg)] = rid
    df["region_id"] = [region_of[(a, b)] for a, b in zip(df["sido"], df["sigungu"])]
    df["sido_code"] = df["region_id"].str[:2]

    raw_ids = df["raw_id"] if "raw_id" in df.columns else [None] * len(df)
    df["key"] = [point_key(la, ln, s, p, rid or None)
                 for la, ln, s, p, rid in zip(df["lat"], df["lng"], df["ssid"], df["place_name"], raw_ids)]
    dup = df["key"].duplicated()
    report["dropped_duplicate_key"] = int(dup.sum())
    df = df[~dup].copy()

    df["install_ym_norm"] = df["install_ym"].map(_norm_ym)
    df["data_date_norm"] = df["data_date"].map(_norm_date)
    df["address"] = df["road_address"].where(df["road_address"].ne(""), df["jibun_address"])
    report["rows_out"] = int(len(df))
    report["regions"] = int(df["region_id"].nunique())
    return df.reset_index(drop=True), report


# ── score ──────────────────────────────────────────────────────
def score_frame(df: pd.DataFrame, tables: R.RuleTables, ref_date: pd.Timestamp) -> pd.DataFrame:
    """정제된 전국(또는 mock) 프레임 전체를 채점한다. R5 경계 판정을 위해 필터 전에 호출할 것."""
    out = df.copy()
    is_open = out["ssid"].map(tables.ssid_labels).eq("open")
    results = {
        "R1": R.r1_secure_access(out, tables),
        "R2": R.r2_facility(out, tables),
        "R3": R.r3_outdoor(out, tables),
        "R4": R.r4_age(out, ref_date),
        "R6": R.r6_operator(out),
        "R7": R.r7_report_path(out),
        "R8": R.r8_data_age(out, ref_date),
    }
    r5_ratio, r5_reason, r5_flag, open_cnt = r5_density(out, is_open)
    results["R5"] = (r5_ratio, r5_reason, r5_flag)
    out["open_ap_within_radius"] = open_cnt.astype(int)
    flag_cols = []
    for rid in RULE_IDS:
        ratio, reason, flag = results[rid]
        n = rid[1:]
        out[f"r{n}"] = ratio.clip(0, 1).round(4)
        out[f"reason{n}"] = reason
        out[f"_flag{n}"] = flag
        flag_cols.append(f"_flag{n}")
    out["flags"] = out[flag_cols].apply(lambda row: ";".join(f for f in row if f), axis=1)
    out = out.drop(columns=flag_cols)
    rcols = [f"r{i}" for i in range(1, 9)]
    sel = [True] * len(RULE_IDS)
    scores = [compute_score(list(v), DEFAULT_WEIGHTS, sel, GRADES, PARAMS) for v in out[rcols].to_numpy()]
    out["score"] = [s.score for s in scores]
    out["grade"] = [s.grade for s in scores]
    for i, w in enumerate(DEFAULT_WEIGHTS, start=1):
        out[f"R{i}_points"] = (out[f"r{i}"] * w).round(2)
    return out
