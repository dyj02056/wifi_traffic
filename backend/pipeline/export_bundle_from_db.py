"""DB(Neon) → 정적 백업 번들 (docs/requests.md #16). 시연 직전에 실행해 web-draft·frontend의 ./data를 최신 DB 기준으로.

지정한 지역만 available로 담고(용량), regions.json·meta.json·key_index.json을 그 지역 기준으로 다시 쓴다.
실행: python pipeline/export_bundle_from_db.py --regions 11-seocho,11-guro [--default 11-seocho]
      → backend/dist/data, 이어서 bash scripts/sync_bundle.sh
"""
import argparse
import shutil

import _bootstrap  # noqa: F401

from wifisafe import db
from wifisafe.bundle import COMPACT_FOLDERS
from wifisafe.io import DIST_DATA_DIR, validate_bundle, write_json

REGION_FOLDERS = ("points", "detail", "changes", "sensitivity")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", required=True)
    ap.add_argument("--default")
    args = ap.parse_args()
    region_ids = [r.strip() for r in args.regions.split(",") if r.strip()]
    default = args.default or region_ids[0]

    with db.connect(direct=True) as conn:
        regions = db.get_doc(conn, "regions.json")
        if regions is None:
            raise SystemExit("DB에 번들 문서가 없습니다 → python pipeline/daily_sync.py 먼저")
        known = {r["region_id"]: r for r in regions["regions"]}
        missing = [r for r in region_ids if r not in known]
        if missing:
            raise SystemExit(f"DB에 없는 region_id: {missing}")
        docs = {rel: db.get_doc(conn, rel) for rel in ("meta.json", "rules.json", "background.json", "cases.json")}
        key_index = {}
        for rid in region_ids:
            for folder in REGION_FOLDERS:
                docs[f"{folder}/{rid}.json"] = db.get_doc(conn, f"{folder}/{rid}.json")
            key_index.update({p["key"]: rid for p in docs[f"points/{rid}.json"]["points"]})

    for r in regions["regions"]:
        r["available"] = r["region_id"] in region_ids
    regions["default_region_id"] = default
    meta = docs["meta.json"]
    meta["regions_in_bundle"] = region_ids
    meta["r1_confirmed"] = all(known[r]["r1_status"] != "provisional" for r in region_ids)
    docs.update({"regions.json": regions, "key_index.json": key_index})

    if DIST_DATA_DIR.exists():
        shutil.rmtree(DIST_DATA_DIR)
    for rel, doc in docs.items():
        write_json(DIST_DATA_DIR / rel, doc, compact=rel.split("/")[0] in COMPACT_FOLDERS)
    errors = validate_bundle(DIST_DATA_DIR)
    if errors:
        raise SystemExit("번들 스키마 검증 실패:\n  " + "\n  ".join(errors[:30]))
    print(f"[export_bundle_from_db] {DIST_DATA_DIR}  지역 {region_ids} (기본 {default}), 스키마 검증 통과")
    print(f"  스냅샷 {meta['snapshot_count']}회, 수집 {meta['snapshot_collected_at']} → bash scripts/sync_bundle.sh")


if __name__ == "__main__":
    main()
