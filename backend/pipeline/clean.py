"""정제: 헤더 매핑, 좌표 검증, region_id·key 부여, 중복 제거 → processed/wifi_clean.parquet

실행: python pipeline/clean.py [--snapshot 2026-10-20]
"""
import argparse
import warnings

import _bootstrap  # noqa: F401

from snapshots import load_raw, resolve
from wifisafe.engine import clean_frame
from wifisafe.io import INTERIM_DIR, PROCESSED_DIR, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    args = ap.parse_args()
    date = resolve(args.snapshot)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")   # 아래에서 직접 출력
        df, report = clean_frame(load_raw(date))
    report["snapshot"] = date
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_DIR / "wifi_clean.parquet", index=False)
    write_json(INTERIM_DIR / "clean_report.json", report)
    print(f"[clean] {date}: 입력 {report['rows_in']:,}행 → 출력 {report['rows_out']:,}행, 시군구 {report['regions']}개")
    print(f"  좌표 위경도 뒤바뀜 수정 {report['coords_swapped_fixed']}, 좌표 불량 제외 {report['dropped_bad_coords']}, "
          f"필수값 결측 제외 {report['dropped_missing_required']}, 중복 key 제외 {report['dropped_duplicate_key']}")
    for sido, n in report["excluded_pending_sido"].items():
        print(f"  ⚠ 경고: '{sido}' {n:,}행 제외 — 공식 시도코드 확인 전 (schema.py PENDING_SIDO, docs/requests.md #11)")
    print(f"  출력: {PROCESSED_DIR / 'wifi_clean.parquet'}")


if __name__ == "__main__":
    main()
