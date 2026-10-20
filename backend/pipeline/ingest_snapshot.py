"""D1 CSV 스냅샷 등록 (plan.md §8.5).

원본 파일을 바이트 그대로 data/raw/snapshots/YYYY-MM-DD.csv 로 복사하고 manifest.csv에 기록한다.
원본은 수정하지 않는다. 날짜는 '수집일'(기본: 오늘).

실행: python pipeline/ingest_snapshot.py <다운로드한 CSV> [--date 2026-10-20] [--force]
"""
import argparse
import hashlib
import shutil
from pathlib import Path

import _bootstrap  # noqa: F401
import pandas as pd

from wifisafe.engine import _norm_date
from wifisafe.io import MANIFEST_PATH, SNAPSHOT_DIR, now_iso, read_csv_any, today, write_csv
from wifisafe.schema import COLUMN_MAP

MANIFEST_COLS = ["snapshot_date", "source_file", "sha256", "encoding", "rows", "columns",
                 "data_reference_date_min", "data_reference_date_max", "header_ok", "ingested_at"]


def load_manifest() -> pd.DataFrame:
    if MANIFEST_PATH.exists():
        return pd.read_csv(MANIFEST_PATH, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return pd.DataFrame(columns=MANIFEST_COLS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--date", default=today(), help="수집일 YYYY-MM-DD (기본 오늘)")
    ap.add_argument("--force", action="store_true", help="같은 날짜에 다른 파일이 있으면 덮어씀")
    args = ap.parse_args()

    src = args.csv.expanduser()
    if not src.exists():
        raise SystemExit(f"파일 없음: {src}")
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    df, enc = read_csv_any(src)
    missing = [c for c in COLUMN_MAP if c not in df.columns]
    header_ok = not missing
    ref_col = next((k for k, v in COLUMN_MAP.items() if v == "data_date"), None)
    dates = df[ref_col].map(_norm_date).dropna() if ref_col in df.columns else pd.Series(dtype=str)

    manifest = load_manifest()
    same_date = manifest[manifest["snapshot_date"] == args.date]
    if len(same_date):
        if same_date["sha256"].iloc[0] == sha:
            print(f"이미 등록된 스냅샷입니다(동일 해시): {args.date}")
            return
        if not args.force:
            raise SystemExit(f"{args.date} 스냅샷이 이미 있고 내용이 다릅니다. 덮어쓰려면 --force")
        manifest = manifest[manifest["snapshot_date"] != args.date]
    dup = manifest[manifest["sha256"] == sha]
    if len(dup):
        print(f"⚠ 경고: {dup['snapshot_date'].iloc[0]} 스냅샷과 내용이 동일합니다(원본 미갱신). 그래도 등록합니다.")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    dst = SNAPSHOT_DIR / f"{args.date}.csv"
    shutil.copyfile(src, dst)
    row = {
        "snapshot_date": args.date, "source_file": src.name, "sha256": sha, "encoding": enc,
        "rows": str(len(df)), "columns": "|".join(df.columns),
        "data_reference_date_min": dates.min() if len(dates) else "",
        "data_reference_date_max": dates.max() if len(dates) else "",
        "header_ok": str(header_ok).lower(), "ingested_at": now_iso(),
    }
    manifest = pd.concat([manifest, pd.DataFrame([row])], ignore_index=True).sort_values("snapshot_date")
    write_csv(MANIFEST_PATH, manifest[MANIFEST_COLS])

    print(f"스냅샷 등록: {dst}")
    print(f"  인코딩={enc}  행 수={len(df):,}  데이터기준일자 {row['data_reference_date_min']} ~ {row['data_reference_date_max']}")
    print(f"  누적 스냅샷 {len(manifest)}회: {', '.join(manifest['snapshot_date'])}")
    if header_ok:
        print("  헤더 확인: COLUMN_MAP과 일치")
    else:
        print(f"  ⚠ 헤더 불일치 — COLUMN_MAP에 있지만 CSV에 없는 컬럼: {missing}")
        print(f"    CSV 실제 헤더: {list(df.columns)}")
        print("    → src/wifisafe/schema.py COLUMN_MAP을 실제 헤더로 고친 뒤 census.py를 실행하세요")


if __name__ == "__main__":
    main()
