"""정제(clean)·채점(score) 공통 로직. pipeline/ 스크립트와 mock 생성기가 같은 코드를 쓴다.

[이 파일이 하는 일]
  1) 사람이 확정한 표(SSID 분류표, 시설 분류표, 실외 단어 목록)를 config/ 폴더에서 읽어 옵니다.
  2) 공공데이터 원본 표를 '정제'합니다: 칸 이름 통일, 위도·경도 뒤바뀜 고치기, 한국 밖 좌표·필수값 빠진 행 버리기,
     지역 번호(region_id)와 지점 고유키(key) 붙이기, 중복 지점 지우기.
  3) 정제된 표 전체를 '채점'합니다: R1~R8 위험비율 → 점수·등급 계산.

[전체 흐름에서의 위치]
  공공데이터 원본(CSV) → ★ clean_frame(정제) → ★ score_frame(채점) → bundle.py(화면용 파일로 내보내기)

[용어 풀이]
  - region_id: 시군구를 가리키는 짧은 이름. 예) "41-goyang"(경기도 고양시). 앞 두 자리는 시도 번호.
  - key: 지점 하나를 구별하는 고유 이름표. 좌표·SSID·장소명으로 만든다(schema.py의 point_key).
  - APP_MODE: dev(개발용, 확정 안 된 데이터도 허용) / final(발표용, 확정된 데이터만 허용)
"""
from __future__ import annotations

import warnings

import pandas as pd

from config.rules import DEFAULT_WEIGHTS, GRADES, PARAMS, RULE_IDS
from wifisafe import rules as R
from wifisafe.density import r5_density
from wifisafe.geo import SUSPECT_FLAG, coord_suspects
from wifisafe.io import CONFIG_DIR, read_config_csv, read_yaml
from wifisafe.schema import (COLUMN_MAP, ID_COLUMN, MOCK_SIDO_CODE, PENDING_SIDO, REQUIRED_INTERNAL, point_key, sido_code,
                             sigungu_slug, validate_header)
from wifisafe.scoring import compute_score

# 한국 영토를 대략 감싸는 네모 범위. 이 밖의 좌표는 잘못 입력된 것으로 본다.
KOREA_BBOX = (33.0, 39.5, 124.0, 132.0)   # lat_min, lat_max, lng_min, lng_max
# SSID 분류표에 허용되는 값: 개방형 / 보안접속 / 불명
VALID_LABELS = {"open", "secure", "unknown"}


# ── 사람이 확정한 표 읽기 + R1 게이트 ─────────────────────────────
# '게이트'는 조건을 못 채우면 작업을 멈추는 검문소라는 뜻이다.
def load_tables():
    """config/ 파일에서 RuleTables를 만든다. 반환: (tables, status dict).

    표를 읽으면서 잘못된 값(허용되지 않는 라벨, 중복 SSID, 0~1 밖 비율)이 있으면 바로 멈춘다.
    status에는 '몇 개가 확정됐는지' 같은 현황 숫자를 담아 meta.json 등에 기록한다.
    """
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
    """SSID 분류표에서 사람이 '확정(confirmed)'한 SSID 이름만 모아 돌려준다."""
    labels = read_config_csv("ssid_labels.csv")
    return set(labels.loc[labels["status"] == "confirmed", "ssid"])


def r1_region_status(df: pd.DataFrame, confirmed: set[str]) -> dict[str, tuple[str, float | None]]:
    """지역별 R1 확정 상태 (requests #23·#24). region_id → (status, coverage).

    coverage = SSID 있는 행 중 확정 라벨이 붙은 행 비율. 기준(R1_REGION_COVERAGE_MIN) 이상이면 confirmed,
    미만이면 provisional('임시(무효)'). SSID가 전부 빈 지역은 확정할 이름이 없으므로 no_ssid(coverage=None).

    예) 고양시 SSID 있는 행 600개 중 570개가 확정 라벨 → coverage 0.95 → confirmed
    """
    has = df["ssid"].fillna("").astype(str).str.strip().ne("")
    ok = df["ssid"].isin(confirmed) & has
    out = {}
    # groupby: 같은 region_id끼리 행을 묶어 지역별로 따로 계산한다.
    for rid, idx in df.groupby("region_id").groups.items():
        n = int(has.loc[idx].sum())
        if n == 0:
            out[rid] = ("no_ssid", None)
            continue
        cov = round(float(ok.loc[idx].sum()) / n, 4)
        out[rid] = ("confirmed" if cov >= PARAMS["R1_REGION_COVERAGE_MIN"] else "provisional", cov)
    return out


def enforce_r1_region_gate(mode: str, region_status: dict, region_ids: list[str]) -> None:
    """발표용(final) 모드인데 SSID 확정 비율이 기준 미만인 지역이 끼어 있으면 작업을 멈춘다."""
    if mode != "final":
        return
    bad = [f"{r}({region_status[r][1]:.1%})" for r in region_ids if region_status[r][0] == "provisional"]
    if bad:
        raise SystemExit(f"APP_MODE=final 이지만 SSID 라벨 확정 비율이 {PARAMS['R1_REGION_COVERAGE_MIN']:.0%} 미만인 지역이 "
                         f"번들에 있습니다: {bad} — 최종 번들 생성 중단")


def enforce_r1_gate(mode: str, status: dict) -> None:
    """발표용(final) 모드인데 SSID 분류표가 전부 확정되지 않았으면 작업을 멈춘다."""
    if mode == "final" and not status["r1_confirmed"]:
        raise SystemExit("APP_MODE=final 이지만 config/ssid_labels.csv가 전부 status=confirmed가 아닙니다. "
                         f"(확정 {status['ssid_labels_confirmed']}/{status['ssid_labels_total']}) — 최종 번들 생성 중단")


# ── clean ──────────────────────────────────────────────────────
def _norm_ym(v: str) -> str | None:
    """설치연월을 'YYYY-MM'(연도만 있으면 'YYYY') 모양으로 통일한다. 해석 불가면 None."""
    ts, year_only = R.parse_install_ym(v)
    if ts is None:
        return None
    return f"{ts.year:04d}" if year_only else f"{ts.year:04d}-{ts.month:02d}"


def _norm_date(v: str) -> str | None:
    """날짜를 'YYYY-MM-DD' 모양으로 통일한다. 해석 불가면 None."""
    d = pd.to_datetime(v or None, errors="coerce", format="mixed")
    return None if pd.isna(d) else d.strftime("%Y-%m-%d")


def clean_frame(raw: pd.DataFrame, mock: bool = False) -> tuple[pd.DataFrame, dict]:
    """공공데이터 원본 표를 채점할 수 있는 깨끗한 표로 바꾼다.

    - raw: 공공데이터 CSV를 그대로 읽은 표 (칸 이름이 한국어)
    - mock: True면 테스트용 가짜 데이터라는 뜻 (지역 번호를 99로 붙임)
    - 돌려주는 값: (정제된 표, 단계별로 몇 행을 고치거나 버렸는지 적은 보고서)
    """
    validate_header(raw.columns)   # 필요한 칸이 다 있는지 먼저 검사
    # 원본의 한국어 칸 이름을 코드에서 쓰는 영어 이름으로 바꾼다 (예: '와이파이SSID' → 'ssid')
    keep = list(COLUMN_MAP) + ([ID_COLUMN] if ID_COLUMN else [])
    df = raw[keep].rename(columns=COLUMN_MAP).copy()
    if ID_COLUMN:
        df = df.rename(columns={ID_COLUMN: "raw_id"})
    for c in df.columns:
        df[c] = df[c].fillna("").astype(str).str.strip()   # 빈칸은 ""로, 앞뒤 공백은 제거
    report = {"rows_in": int(len(df))}

    # 1) 좌표 정리: 숫자로 바꾸고, 위도·경도가 뒤바뀐 행은 서로 바꿔 고친다.
    #    한국의 위도는 33~39.5, 경도는 124~132 정도라서 위도 칸에 124~132가 들어 있으면 뒤바뀐 것이다.
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    swapped = df["lat"].between(124, 132) & df["lng"].between(33, 39.5)
    df.loc[swapped, ["lat", "lng"]] = df.loc[swapped, ["lng", "lat"]].to_numpy()
    report["coords_swapped_fixed"] = int(swapped.sum())
    # 2) 한국 범위 밖 좌표는 버린다.
    lat0, lat1, lng0, lng1 = KOREA_BBOX
    bad_xy = ~(df["lat"].between(lat0, lat1) & df["lng"].between(lng0, lng1))
    report["dropped_bad_coords"] = int(bad_xy.sum())
    df = df[~bad_xy]
    # 3) 장소명·시도·시군구 중 하나라도 비면 지도에 올릴 수 없으므로 버린다.
    missing_req = pd.Series(False, index=df.index)
    for c in ("place_name", "sido", "sigungu"):
        missing_req |= df[c].eq("")
    report["dropped_missing_required"] = int(missing_req.sum())
    df = df[~missing_req].copy()
    # 4) 시도 번호를 아직 확인하지 못한 시도는 잠시 제외한다(schema.py PENDING_SIDO).
    pending = df["sido"].isin(PENDING_SIDO) if not mock else pd.Series(False, index=df.index)
    report["excluded_pending_sido"] = {k: int(v) for k, v in df.loc[pending, "sido"].value_counts().items()}
    if report["excluded_pending_sido"]:
        warnings.warn(f"시도코드 확인 전이라 제외: {report['excluded_pending_sido']} (schema.py PENDING_SIDO)", stacklevel=2)
    df = df[~pending].copy()
    assert all(c in df.columns for c in REQUIRED_INTERNAL)

    # region_id
    # 5) (시도, 시군구) 쌍마다 지역 번호를 붙인다. 이름이 겹치면 뒤에 -2, -3을 붙여 구별한다.
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

    # 6) 지점마다 고유키를 만들고, 같은 키가 두 번 나오면 뒤의 것을 지운다(중복 제거).
    raw_ids = df["raw_id"] if "raw_id" in df.columns else [None] * len(df)
    df["key"] = [point_key(la, ln, s, p, rid or None)
                 for la, ln, s, p, rid in zip(df["lat"], df["lng"], df["ssid"], df["place_name"], raw_ids)]
    dup = df["key"].duplicated()
    report["dropped_duplicate_key"] = int(dup.sum())
    df = df[~dup].copy()

    # 7) 날짜 모양 통일, 주소는 도로명 주소가 있으면 그것을, 없으면 지번 주소를 쓴다.
    df["install_ym_norm"] = df["install_ym"].map(_norm_ym)
    df["data_date_norm"] = df["data_date"].map(_norm_date)
    df["address"] = df["road_address"].where(df["road_address"].ne(""), df["jibun_address"])
    report["rows_out"] = int(len(df))
    report["regions"] = int(df["region_id"].nunique())
    return df.reset_index(drop=True), report


# ── score ──────────────────────────────────────────────────────
def score_frame(df: pd.DataFrame, tables: R.RuleTables, ref_date: pd.Timestamp) -> pd.DataFrame:
    """정제된 전국(또는 mock) 프레임 전체를 채점한다. R5 경계 판정을 위해 필터 전에 호출할 것.

    (R5 밀집도는 이웃 시군구 지점도 봐야 경계 표시를 붙일 수 있어서, 지역별로 자르기 전 전국 표로 채점한다.)
    결과 표에 r1~r8(위험비율), reason1~8(이유), flags(문제 표식), score(점수), grade(등급),
    R1_points~R8_points(요인별 기본 점수) 칸이 추가된다.
    """
    out = df.copy()
    is_open = out["ssid"].map(tables.ssid_labels).eq("open")   # 개방형 AP인지 (R5 밀집도 계산용)
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
    # 요인별 결과를 r1, reason1, _flag1 … 칸으로 표에 붙인다. 위험비율은 0~1로 자르고 소수 넷째 자리까지.
    flag_cols = []
    for rid in RULE_IDS:
        ratio, reason, flag = results[rid]
        n = rid[1:]   # "R1" → "1"
        out[f"r{n}"] = ratio.clip(0, 1).round(4)
        out[f"reason{n}"] = reason
        out[f"_flag{n}"] = flag
        flag_cols.append(f"_flag{n}")
    out["_flag_coord"] = coord_suspects(out).map({True: SUSPECT_FLAG, False: ""})   # 표시만, 점수 영향 없음 (#32)
    flag_cols.append("_flag_coord")
    # 흩어진 flag 칸들을 "R1_unknown;R4_missing"처럼 세미콜론으로 이어 한 칸(flags)에 모은다.
    out["flags"] = out[flag_cols].apply(lambda row: ";".join(f for f in row if f), axis=1)
    out = out.drop(columns=flag_cols)
    # 기본 기준(8개 모두 켜고 기본 가중치)으로 모든 지점의 점수·등급을 계산한다.
    rcols = [f"r{i}" for i in range(1, 9)]
    sel = [True] * len(RULE_IDS)
    scores = [compute_score(list(v), DEFAULT_WEIGHTS, sel, GRADES, PARAMS) for v in out[rcols].to_numpy()]
    out["score"] = [s.score for s in scores]
    out["grade"] = [s.grade for s in scores]
    # 요인별 기본 점수 = 위험비율 × 가중치 (지점 상세 화면에 '이 요인 때문에 몇 점'으로 표시)
    for i, w in enumerate(DEFAULT_WEIGHTS, start=1):
        out[f"R{i}_points"] = (out[f"r{i}"] * w).round(2)
    return out
