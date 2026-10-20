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
from wifisafe.background import build_background
from wifisafe.cases import load_cases
from wifisafe.changes import CHANGE_COLS
from wifisafe.engine import enforce_r1_gate, load_tables
from wifisafe.io import (CONFIG_DIR, DIST_DATA_DIR, GOLDEN_PATH, INTERIM_DIR, PROCESSED_DIR, app_mode, read_json,
                         read_yaml, validate_bundle, write_json)


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
    unknown = sorted(set(region_ids) - set(scored["region_id"]))
    if unknown:
        known = scored.drop_duplicates("region_id").set_index("region_id")
        hint = known[known["sido"] == "서울특별시"]["sigungu"].to_dict() if "sido" in known else {}
        raise SystemExit(f"없는 region_id: {unknown}. 예시(서울): {dict(list(hint.items())[:30])}")
    default = args.default or region_ids[0]

    snap = read_json(INTERIM_DIR / "clean_report.json")["snapshot"]
    dates = snapshot_dates()
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

    src_cfg = read_yaml(CONFIG_DIR / "sources.yaml")["sources"]
    d1 = src_cfg["D1"]
    sources = [{"id": "D1", "name": d1["name"], "dataset_id": d1["dataset_id"], "url": d1["url"], "retrieved_at": snap}]
    background, bg_warn = build_background()
    used = {d["source"]["name"] for d in background["datasets"]}
    for sid in ("D3", "D4", "D5"):
        s = src_cfg.get(sid) or {}
        if s.get("name") in used:
            ds = next(d for d in background["datasets"] if d["source"]["name"] == s["name"])
            sources.append({"id": sid, "name": s["name"], "dataset_id": s.get("dataset_id"), "url": s["url"],
                            "retrieved_at": ds["source"]["retrieved_at"]})
    cases = load_cases()

    meta = B.meta_json(is_mock=False, r1_confirmed=status["r1_confirmed"], app_mode=mode,
                       data_reference_date=scored["data_date_norm"].dropna().max(), snapshot_collected_at=snap,
                       snapshot_count=len(dates), regions_in_bundle=region_ids, sources=sources)
    regions = B.regions_json(scored, set(region_ids), default)

    if DIST_DATA_DIR.exists():
        shutil.rmtree(DIST_DATA_DIR)
    B.write_bundle(DIST_DATA_DIR, meta=meta, regions=regions, scored=scored, region_ids=region_ids, changes=changes,
                   snapshots=dates, background=background, cases=cases, explanations=explanations)
    errors = validate_bundle(DIST_DATA_DIR)
    if errors:
        raise SystemExit("번들 스키마 검증 실패:\n  " + "\n  ".join(errors[:30]))

    print(f"[export_bundle] {DIST_DATA_DIR}  APP_MODE={mode}  r1_confirmed={status['r1_confirmed']}  스키마 검증 통과")
    for rid in region_ids:
        sub = scored[scored["region_id"] == rid]
        n_exp = len(explanations.get(rid, {}))
        print(f"  {rid}: 지점 {len(sub):,}개, 사전 생성 설명 {n_exp}개(나머지 템플릿), 등급 {sub['grade'].value_counts().to_dict()}")
    print(f"  스냅샷 {len(dates)}회, 배경 통계 {len(background['datasets'])}종, 사례 카드 {len(cases['cases'])}건")
    for w in bg_warn:
        print(f"  ⚠ 배경: {w}")
    if not status["r1_confirmed"]:
        print("  ⚠ 개발용 번들(meta.r1_confirmed=false) — 화면에 '임시(무효)' 워터마크가 표시됩니다")

    if not args.no_golden:
        sample = (scored[scored["region_id"].isin(region_ids)].sort_values("key")
                  [[f"r{i}" for i in range(1, 9)]].head(15).to_numpy().tolist())
        golden = B.golden_json(sample, "real")
        write_json(GOLDEN_PATH, golden)
        print(f"  golden 갱신: {GOLDEN_PATH} ({len(golden['cases'])}건) → scripts/sync_bundle 후 세 구현 테스트 재실행")


if __name__ == "__main__":
    main()
