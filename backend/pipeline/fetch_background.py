"""배경 통계(D3~D5) 수집 → data/external/*.csv (점수 미반영, plan.md §5)

[이 파일이 하는 일]
  공공데이터포털(data.go.kr)의 API에서 경찰청·KISA 통계를 내려받아 CSV로 저장합니다.
  (D3 = 경찰청 사이버범죄 통계, D4 = KISA 업종별 침해사고, D5 = KISA 민간 침해사고)
  API는 한 번에 최대 1000행만 주므로 쪽(page)을 넘기며 끝까지 받습니다.
  저장한 CSV는 background.py가 /context 화면용 차트로 바꿉니다. 점수에는 쓰지 않습니다.
  API 대신 CSV를 직접 받아 import_downloads.py로 넣어도 됩니다.

config/sources.yaml 각 소스의 endpoint(Swagger에서 복사)와 .env의 DATA_GO_KR_KEY가 있어야 한다. 추측 URL 금지.
odcloud 자동변환 API 응답({"data": [...], "totalCount": N})을 page/perPage로 끝까지 받는다.
수집 시각은 같은 이름의 .meta.json(retrieved_at)에 기록하고, background.json이 출처 날짜로 쓴다.

실행: python pipeline/fetch_background.py [--only D3]
"""
import argparse
import json
import os
import urllib.parse
import urllib.request

import _bootstrap  # noqa: F401
import pandas as pd

from wifisafe.io import BACKEND_DIR, CONFIG_DIR, read_yaml, today, write_csv, write_json

PER_PAGE = 1000   # 한 번에 받을 행 수


def fetch_all(endpoint: str, key: str) -> list[dict]:
    """API 주소에서 모든 행을 받아 목록으로 돌려준다. 받은 행 수가 전체 수(totalCount)에 이르면 멈춘다."""
    rows, page = [], 1
    while True:
        q = urllib.parse.urlencode({"page": page, "perPage": PER_PAGE, "returnType": "JSON", "serviceKey": key})
        sep = "&" if "?" in endpoint else "?"
        with urllib.request.urlopen(f"{endpoint}{sep}{q}", timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        data = body.get("data")
        if data is None:
            raise SystemExit(f"예상과 다른 응답(키 'data' 없음): {str(body)[:300]}")
        rows += data
        total = body.get("totalCount") or body.get("matchCount") or len(rows)
        if not data or len(rows) >= total:
            return rows
        page += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="D3,D4,D5 중 일부")
    args = ap.parse_args()
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    sources = read_yaml(CONFIG_DIR / "sources.yaml")["sources"]
    targets = [s.strip() for s in (args.only or "D3,D4,D5").split(",")]
    for sid in targets:
        src = sources.get(sid) or {}
        if not src.get("endpoint"):
            print(f"[{sid}] endpoint 없음 — 건너뜀 (CSV를 downloads/에 받아 import_downloads.py로 넣는 방식 권장)")
            continue
        if not key:
            raise SystemExit(".env에 DATA_GO_KR_KEY가 없습니다 (data.go.kr 활용신청 후 일반 인증키)")
        rows = fetch_all(src["endpoint"], key)
        out = BACKEND_DIR / src["file"]
        write_csv(out, pd.DataFrame(rows))
        write_json(out.with_suffix(".meta.json"), {"source": sid, "endpoint": src["endpoint"], "rows": len(rows),
                                                   "retrieved_at": today()})
        print(f"[{sid}] {len(rows)}행 → {out}")
        if rows:
            print(f"  컬럼: {list(rows[0].keys())}  → sources.yaml background_charts에 label/value 컬럼을 지정하세요")


if __name__ == "__main__":
    main()
