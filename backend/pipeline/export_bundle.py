"""정적 데이터 번들 생성 + 스키마 검증 + golden_scores.json 갱신 (plan.md §6, M3)

입력: processed/wifi_scored.parquet, processed/wifi_changes.csv, processed/explanations/, data/cases.yaml,
      config/sources.yaml(background_charts)
출력: dist/data/ (contracts/schemas 10종 준수), contracts/golden_scores.json (실데이터 샘플 포함)
APP_MODE=final 에서 R1 라벨 미확정이면 에러로 종료.

실행: python pipeline/export_bundle.py --regions 11-guro [--default 11-guro] [--no-golden]
"""
import argparse
import shutil

import _bootstrap  # noqa: F401
import pandas as pd

from snapshots import snapshot_dates
from wifisafe import bundle as B
from wifisafe.assemble import assemble, print_summary
from wifisafe.changes import CHANGE_COLS
from wifisafe.engine import enforce_r1_gate, load_tables
from wifisafe.io import DIST_DATA_DIR, GOLDEN_PATH, INTERIM_DIR, PROCESSED_DIR, app_mode, read_json, validate_bundle, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", required=True, help="번들에 넣을 region_id, 쉼표 구분 (예: 11-guro)")
    ap.add_argument("--default", help="regions.json default_region_id (기본: --regions 첫 번째)")
    ap.add_argument("--no-golden", action="store_true")
    args = ap.parse_args()

    mode = app_mode()
    _, status = load_tables()
    enforce_r1_gate(mode, status)
    scored = pd.read_parquet(PROCESSED_DIR / "wifi_scored.parquet")
    region_ids = [r.strip() for r in args.regions.split(",") if r.strip()]

    snap = read_json(INTERIM_DIR / "clean_report.json")["snapshot"]
    ch_path = PROCESSED_DIR / "wifi_changes.csv"
    changes = (pd.read_csv(ch_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
               if ch_path.exists() else pd.DataFrame(columns=CHANGE_COLS))
    if "region_id" not in changes.columns:
        changes["region_id"] = []
    explanations = {}
    for rid in region_ids:
        p = PROCESSED_DIR / "explanations" / f"{rid}.json"
        if p.exists():
            explanations[rid] = read_json(p)

    a = assemble(scored, region_ids, args.default or region_ids[0], mode=mode, snapshot=snap,
                 snapshot_dates=snapshot_dates(), changes=changes, explanations=explanations)
    if DIST_DATA_DIR.exists():
        shutil.rmtree(DIST_DATA_DIR)
    B.write_bundle(DIST_DATA_DIR, **a.docs_kwargs)
    errors = validate_bundle(DIST_DATA_DIR)
    if errors:
        raise SystemExit("번들 스키마 검증 실패:\n  " + "\n  ".join(errors[:30]))
    print(f"[export_bundle] {DIST_DATA_DIR}  APP_MODE={mode}  스키마 검증 통과")
    print_summary("export_bundle", a, scored, region_ids)

    if not args.no_golden:
        sample = (scored[scored["region_id"].isin(region_ids)].sort_values("key")
                  [[f"r{i}" for i in range(1, 9)]].head(15).to_numpy().tolist())
        golden = B.golden_json(sample, "real")
        write_json(GOLDEN_PATH, golden)
        print(f"  golden 갱신: {GOLDEN_PATH} ({len(golden['cases'])}건) → scripts/sync_bundle 후 세 구현 테스트 재실행")


if __name__ == "__main__":
    main()
