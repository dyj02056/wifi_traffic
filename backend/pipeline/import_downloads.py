"""downloads/ 폴더에 받아 둔 원본 파일을 파이프라인 위치로 옮긴다.

  downloads/D1_전국무료와이파이/*.csv  → ingest_snapshot (수집일 = 파일 수정일, --date로 지정 가능)
  downloads/D2_구로구와이파이/*.csv     → backend/data/external/guro_wifi.csv
  downloads/D3_경찰청사이버범죄/*.csv   → backend/data/external/police_cyber.csv
  downloads/D4_KISA업종별침해사고/*.csv → backend/data/external/kisa_industry.csv
  downloads/D5_KISA민간침해사고/*.csv   → backend/data/external/kisa_private.csv
D2~D5는 폴더 안 가장 최근 CSV 하나를 쓰고, 수집일을 같은 이름의 .meta.json(retrieved_at)에 남긴다.
원본 파일은 지우지 않는다.

실행: python pipeline/import_downloads.py [--date 2026-10-20]
"""
import argparse
import shutil
import subprocess
import sys
from datetime import datetime

import _bootstrap  # noqa: F401

from snapshots import snapshot_dates
from wifisafe.io import BACKEND_DIR, REPO_DIR, read_csv_any, write_json

DOWNLOADS = REPO_DIR / "downloads"
EXTERNAL = {
    "D2": ("D2_구로구와이파이", "guro_wifi.csv"),
    "D3": ("D3_경찰청사이버범죄", "police_cyber.csv"),
    "D4": ("D4_KISA업종별침해사고", "kisa_industry.csv"),
    "D5": ("D5_KISA민간침해사고", "kisa_private.csv"),
}
D1_DIR = "D1_전국무료와이파이"


def mdate(p) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="D1 수집일(기본: 파일 수정일)")
    args = ap.parse_args()

    d1 = sorted((DOWNLOADS / D1_DIR).glob("*.csv"), key=lambda p: p.stat().st_mtime)
    print(f"[D1] {len(d1)}개 파일")
    for p in d1:
        date = args.date or mdate(p)
        if date in snapshot_dates():
            print(f"  {p.name}: {date} 스냅샷이 이미 있음 — 건너뜀 (덮어쓰려면 ingest_snapshot.py --force)")
            continue
        subprocess.run([sys.executable, str(BACKEND_DIR / "pipeline" / "ingest_snapshot.py"), str(p), "--date", date],
                       check=True)

    for sid, (folder, target) in EXTERNAL.items():
        files = sorted((DOWNLOADS / folder).glob("*.csv"), key=lambda p: p.stat().st_mtime)
        if not files:
            print(f"[{sid}] 파일 없음 — 건너뜀 (downloads/{folder}/)")
            continue
        src = files[-1]
        dst = BACKEND_DIR / "data" / "external" / target
        shutil.copyfile(src, dst)
        df, enc = read_csv_any(dst)
        write_json(dst.with_suffix(".meta.json"), {"source": sid, "original_file": src.name, "rows": len(df),
                                                   "encoding": enc, "retrieved_at": mdate(src)})
        print(f"[{sid}] {src.name} → {dst} ({len(df)}행, {enc}, 수집일 {mdate(src)})")
        print(f"  컬럼: {list(df.columns)}")


if __name__ == "__main__":
    main()
