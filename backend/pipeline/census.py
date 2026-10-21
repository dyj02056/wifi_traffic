"""스냅샷 census — SSID·시설구분·설치장소상세 고유값 집계, 행 수/고유 장소 수 기록 (plan.md §8.3, M1).

[이 파일이 하는 일]
  census는 '전수조사'라는 뜻입니다. 원본 데이터를 훑어서 "어떤 SSID가 몇 번 나오나", "시설구분 값은 몇 종류인가",
  "빈칸 비율은 얼마인가" 같은 현황표를 만듭니다. 사람이 분류표(ssid_labels.csv, facility_map.csv, keywords.yaml)를
  채울 때 이 현황표를 보고 작업합니다. 채점 자체는 하지 않습니다.

[언제 쓰나]
  새 스냅샷을 받은 직후, 또는 분류표를 고치기 전에 현황을 볼 때.

출력(data/interim/):
  header.json               실제 헤더와 COLUMN_MAP 비교
  ssid_census.csv           SSID 고유값·빈도·누적비율·예시 시군구·현재 라벨 → ssid_labels.csv 작성용
  facility_census.csv       설치시설구분 고유값·빈도·예시 → facility_map.csv 작성용
  place_detail_census.csv   설치장소상세 상위 문구 + 실외 키워드 매칭 → keywords.yaml 확정용
  census_summary.json       행 수, 고유 장소 수, 결측률, 형식 분포, 라벨 커버리지

실행: python pipeline/census.py [--snapshot 2026-10-20]
"""
import argparse
import re

import _bootstrap  # noqa: F401
import pandas as pd

from snapshots import load_raw, resolve
from wifisafe.engine import clean_frame, load_tables
from wifisafe.io import INTERIM_DIR, write_csv, write_json
from wifisafe.schema import COLUMN_MAP, COLUMN_MAP_STATUS, ID_COLUMN, SIDO_CODES


def shape(v: str) -> str:
    """값의 형식 패턴: 숫자→9, 한글→가, 영문→A (예: '2017-03' → '9999-99')."""
    s = re.sub(r"\d", "9", str(v))
    s = re.sub(r"[가-힣]", "가", s)
    return re.sub(r"[A-Za-z]", "A", s) or "(빈값)"


def label_coverage(df: pd.DataFrame, labels: pd.DataFrame) -> dict:
    """SSID 분류표가 전체 행의 몇 %를 덮는지(라벨 있음 / 확정 라벨 / SSID가 있는 행 중 확정) 계산한다."""
    confirmed = set(labels.loc[labels["status"] == "confirmed", "ssid"])
    anyl = set(labels["ssid"])
    n = len(df)
    ne = df[df["ssid"] != ""]
    return {
        "rows_nonempty_ssid": int(len(ne)),
        "coverage_confirmed_nonempty": round(ne["ssid"].isin(confirmed).mean(), 4) if len(ne) else 0,
        "rows": n,
        "rows_with_any_label": int(df["ssid"].isin(anyl).sum()),
        "rows_with_confirmed_label": int(df["ssid"].isin(confirmed).sum()),
        "coverage_any": round(df["ssid"].isin(anyl).mean(), 4) if n else 0,
        "coverage_confirmed": round(df["ssid"].isin(confirmed).mean(), 4) if n else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    args = ap.parse_args()
    date = resolve(args.snapshot)
    raw = load_raw(date)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 칸 이름 검사: COLUMN_MAP에 있는데 CSV에 없는 칸(missing)이 있으면 멈춘다
    cols = list(raw.columns)
    missing = [c for c in COLUMN_MAP if c not in cols]
    extra = [c for c in cols if c not in COLUMN_MAP and c != ID_COLUMN]
    write_json(INTERIM_DIR / "header.json", {"snapshot": date, "columns": cols, "column_map_status": COLUMN_MAP_STATUS,
                                             "missing_from_csv": missing, "not_in_column_map": extra,
                                             "sample_rows": raw.head(3).to_dict(orient="records")})
    print(f"[census] 스냅샷 {date}: {len(raw):,}행, 컬럼 {len(cols)}개")
    print(f"  실제 헤더: {cols}")
    if missing:
        print(f"  ⚠ COLUMN_MAP 불일치: CSV에 없는 컬럼 {missing}")
        print(f"    COLUMN_MAP에 없는 CSV 컬럼 {extra}")
        raise SystemExit("  → src/wifisafe/schema.py COLUMN_MAP을 고친 뒤 다시 실행하세요 (data/interim/header.json 참고)")
    if extra:
        print(f"  참고: COLUMN_MAP에 없는(사용하지 않는) 컬럼 {extra}")

    df = raw[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    for c in df.columns:
        df[c] = df[c].fillna("").astype(str).str.strip()
    tables, status = load_tables()
    labels = pd.read_csv(_bootstrap.BACKEND / "config" / "ssid_labels.csv", dtype=str, keep_default_na=False,
                         encoding="utf-8-sig")
    lab = dict(zip(labels["ssid"], labels["label"]))
    st = dict(zip(labels["ssid"], labels["status"]))

    # SSID
    # 2) SSID별 행 수·나오는 시군구 수·예시를 세고, 많이 나온 순으로 정렬해 누적 비율(cum_share)을 붙인다.
    #    누적 비율을 보면 "상위 몇 개 SSID만 분류하면 전체의 몇 %가 해결되는지" 알 수 있다.
    g = df.groupby("ssid")
    ssid = pd.DataFrame({"rows": g.size(), "n_sigungu": g["sigungu"].nunique(),
                         "example_sigungu": g.apply(lambda x: " / ".join((x["sido"] + " " + x["sigungu"]).value_counts().index[:3]), include_groups=False),
                         "example_provider": g["provider"].agg(lambda s: " / ".join(s.value_counts().index[:2]))})
    ssid = ssid.sort_values("rows", ascending=False).reset_index()
    ssid["share"] = (ssid["rows"] / len(df)).round(5)
    ssid["cum_share"] = ssid["share"].cumsum().round(5)
    ssid["current_label"] = ssid["ssid"].map(lab).fillna("")
    ssid["current_status"] = ssid["ssid"].map(st).fillna("")
    write_csv(INTERIM_DIR / "ssid_census.csv", ssid)

    # 시설구분
    g = df.groupby("facility_type")
    fac = pd.DataFrame({"rows": g.size(),
                        "example_place_detail": g["place_detail"].agg(lambda s: " / ".join(s.value_counts().index[:3])),
                        "example_place_name": g["place_name"].agg(lambda s: " / ".join(s.value_counts().index[:3]))})
    fac = fac.sort_values("rows", ascending=False).reset_index()
    fac["share"] = (fac["rows"] / len(df)).round(5)
    fac["mapped_ratio"] = fac["facility_type"].map(lambda v: tables.facility_map.get(v, ("", ""))[0])
    write_csv(INTERIM_DIR / "facility_census.csv", fac)

    # 설치장소상세
    det = df["place_detail"].value_counts().head(500).rename_axis("place_detail").reset_index(name="rows")
    det["outdoor_keyword_hit"] = det["place_detail"].map(
        lambda s: next((k for k in tables.outdoor_keywords if k in s), ""))
    write_csv(INTERIM_DIR / "place_detail_census.csv", det)

    # 요약
    # 3) 전체 요약: 행 수, 고유 장소 수, 칸별 빈칸 비율, 날짜·전화번호 모양 분포, 라벨 커버리지
    try:
        clean, report = clean_frame(raw)
    except SystemExit as e:      # 예: 시도코드 미등록 — 요약은 남기고 사유를 기록
        clean, report = pd.DataFrame({"data_date_norm": pd.Series(dtype=object)}), {"error": str(e)}
        print(f"  ⚠ clean 단계 확인 필요: {e}")
    addr = df["road_address"].where(df["road_address"].ne(""), df["jibun_address"])
    summary = {
        "snapshot": date,
        "rows": int(len(df)),
        "unique_places_name_address": int(pd.DataFrame({"a": df["sido"], "b": df["sigungu"], "c": df["place_name"],
                                                       "d": addr}).drop_duplicates().shape[0]),
        "unique_coordinates_5dp": int(pd.DataFrame({"a": pd.to_numeric(df["lat"], errors="coerce").round(5),
                                                    "b": pd.to_numeric(df["lng"], errors="coerce").round(5)}).drop_duplicates().shape[0]),
        "unique_ssid": int(df["ssid"].nunique()),
        "unique_facility_type": int(df["facility_type"].nunique()),
        "sido_values": sorted(df["sido"].unique().tolist()),
        "sido_without_code": sorted(set(df["sido"]) - set(SIDO_CODES)),
        "null_rate": {c: round(float(df[c].eq("").mean()), 4) for c in df.columns},
        "install_ym_shapes": df["install_ym"].map(shape).value_counts().head(10).to_dict(),
        "data_date_shapes": df["data_date"].map(shape).value_counts().head(10).to_dict(),
        "manager_tel_shapes": df["manager_tel"].map(shape).value_counts().head(10).to_dict(),
        "data_date_range": ([clean["data_date_norm"].dropna().min(), clean["data_date_norm"].dropna().max()] if clean["data_date_norm"].notna().any() else None),
        "clean_report": report,
        "ssid_label_coverage": label_coverage(df, labels),
        "label_status": status,
        "note": "rows는 표준데이터 행 수, unique_places_*는 고유 장소 수 추정치. 기획안의 '4만7089곳'(국회 제출 설치 장소 수)과 같은 의미로 섞어 쓰지 않는다.",
    }
    write_json(INTERIM_DIR / "census_summary.json", summary)
    if summary["sido_without_code"]:
        print(f"  ⚠ 시도코드 미등록 시도명: {summary['sido_without_code']} → schema.py SIDO_CODES에 추가 필요")
    print(f"  행 수 {summary['rows']:,} / 고유 장소(시도·시군구·장소명·주소) {summary['unique_places_name_address']:,} / "
          f"고유 좌표 {summary['unique_coordinates_5dp']:,}")
    print(f"  고유 SSID {summary['unique_ssid']:,}개, 고유 시설구분 {summary['unique_facility_type']:,}개")
    top = ssid.head(10)[["ssid", "rows", "cum_share"]].to_string(index=False)
    print("  SSID 상위 10:\n    " + top.replace("\n", "\n    "))
    cov = summary["ssid_label_coverage"]
    print(f"  SSID 라벨 커버리지(행 기준): 확정 {cov['coverage_confirmed']:.1%}, 라벨 있음 {cov['coverage_any']:.1%}, "
          f"SSID 있는 행 중 확정 {cov['coverage_confirmed_nonempty']:.1%} (M2 목표 95%는 이 값 기준)")
    print(f"  출력: {INTERIM_DIR}")


if __name__ == "__main__":
    main()
