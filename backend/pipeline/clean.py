"""정제: 헤더 매핑, 좌표 검증, region_id·key 부여, 중복 제거 → processed/wifi_clean.parquet

[이 파일이 하는 일]
  원본 데이터(스냅샷 하나)를 정제해서 data/processed/wifi_clean.parquet로 저장하고,
  몇 행을 고치거나 버렸는지 data/interim/clean_report.json에 기록합니다.
  (parquet: 표를 빠르게 읽고 쓰기 좋게 압축 저장하는 파일 형식)
  정제 규칙은 src/wifisafe/engine.py의 clean_frame에 있습니다.

[순서] ingest_snapshot.py(원본 등록) → ★ clean.py → score.py → export_bundle.py

실행: python pipeline/clean.py [--snapshot 2026-10-20]
(--snapshot을 빼면 가장 최근 스냅샷을 쓴다)
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
