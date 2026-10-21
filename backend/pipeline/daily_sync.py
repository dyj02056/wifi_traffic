"""매일 수집: LOCALDATA 전국 무료와이파이 CSV → 정제·채점 → Neon (docs/requests.md #15·#17)

1. 원본 다운로드(sources.yaml D1.download_url, 키 불필요). 해시가 이미 등록된 스냅샷과 같으면 종료(--force로 재처리)
2. clean_frame → DB의 직전 최신본(wifi_current)과 비교해 추가·삭제 이력(wifi_changes) 추가
3. 전국 score_frame (R5 점수는 같은 시군구 AP만 세고, 전국 데이터로 경계 근처 지점에 R5_boundary flag만 붙임 — density.py)
4. 전 지역 번들 문서(contracts/ 스키마)를 만들어 스키마 검증 후 bundle_docs에 저장
2~4는 한 트랜잭션: 중간에 실패하면 DB는 이전 상태 그대로다. 원본 파일은 DB에 저장하지 않는다(무료 0.5GB).

실행: python pipeline/daily_sync.py [--csv 로컬CSV] [--date YYYY-MM-DD] [--force] [--default 11-seocho]
      (GitHub Actions: .github/workflows/daily-sync.yml, DATABASE_URL은 Secrets)
"""
import argparse
import hashlib
import tempfile
import time
import urllib.request
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _bootstrap  # noqa: F401
import pandas as pd

from wifisafe import bundle as B
from wifisafe import db
from wifisafe.assemble import assemble, print_summary
from wifisafe.background import build_background
from wifisafe.changes import CHANGE_COLS, diff_snapshots
from wifisafe.engine import clean_frame, enforce_r1_gate, load_tables, score_frame
from wifisafe.io import CONFIG_DIR, app_mode, read_csv_any, read_yaml, schema_name_for, validator_for

KST = timezone(timedelta(hours=9))
DEFAULT_REGION = "41-goyang"   # requests #34 (라벨·R2 확정 후 재비교로 확정)


def download(url: str, referer: str | None, dst: Path) -> None:
    headers = {"User-Agent": "Mozilla/5.0 (wifi-traffic daily_sync)"}
    if referer:
        headers["Referer"] = referer
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as resp:
                body = resp.read()
            if body[:200].lstrip().lower().startswith((b"<!doctype", b"<html")):
                raise RuntimeError("CSV 대신 HTML이 왔습니다(다운로드 주소·차단 여부 확인)")
            dst.write_bytes(body)
            return
        except Exception as e:  # noqa: BLE001 — 네트워크 오류는 재시도 후 그대로 알린다
            if attempt == 2:
                raise SystemExit(f"원본 다운로드 실패: {e}")
            time.sleep(10 * (attempt + 1))


def validated(docs):
    """문서를 내보내기 전에 contracts/ 스키마로 검증한다(하나라도 틀리면 저장하지 않고 중단)."""
    cache = {}
    for rel, doc in docs:
        name = schema_name_for(rel)
        if name:
            v = cache.get(name) or cache.setdefault(name, validator_for(name))
            err = next(iter(v.iter_errors(doc)), None)
            if err is not None:
                raise SystemExit(f"스키마 검증 실패 {rel}: {'/'.join(map(str, err.absolute_path))}: {err.message}")
        yield rel, doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, help="다운로드 대신 이 파일을 쓴다(테스트·재처리용)")
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"), help="수집일 (기본: 오늘, KST)")
    ap.add_argument("--force", action="store_true", help="같은 원본이 이미 등록돼 있어도 다시 처리")
    ap.add_argument("--default", default=DEFAULT_REGION, help="regions.json default_region_id")
    args = ap.parse_args()

    t0 = time.time()
    mode = app_mode()
    tables, status = load_tables()
    enforce_r1_gate(mode, status)
    d1 = read_yaml(CONFIG_DIR / "sources.yaml")["sources"]["D1"]

    with tempfile.TemporaryDirectory() as tmp:
        src = args.csv
        if src is None:
            src = Path(tmp) / "free_wifi_info.csv"
            download(d1["download_url"], d1.get("download_referer"), src)
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        raw, enc = read_csv_any(src)
    print(f"[daily_sync] {args.date} 원본 {len(raw):,}행 ({enc}, sha256 {sha[:12]}…)")

    with db.connect(direct=True) as conn:
        db.migrate(conn)
        same = db.snapshot_by_sha(conn, sha)
        if same and not args.force:
            print(f"  원본이 {same} 스냅샷과 같습니다(갱신 없음) → 종료. 다시 처리하려면 --force")
            return

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clean, report = clean_frame(raw)
        print(f"  정제 {report['rows_in']:,} → {report['rows_out']:,}행, 시군구 {report['regions']}개")
        for sido, n in report["excluded_pending_sido"].items():
            print(f"  ⚠ '{sido}' {n:,}행 제외 — 공식 시도코드 확인 전 (requests #11)")

        prev_dates = [d for d in db.snapshot_dates(conn) if d != args.date]
        prev = db.load_current(conn)
        if prev_dates and len(prev):
            new_changes = diff_snapshots(prev, clean, prev_dates[-1], args.date)
            # 이전 수집에 아예 없던 지역(시도코드 신규 등록 등)은 이번이 첫 수집 — 전 지점을 '신규 설치'로 남기지 않는다 (#38)
            first_seen = set(clean["region_id"]) - set(prev["region_id"])
            if first_seen:
                new_changes = new_changes[~new_changes["region_id"].isin(first_seen)]
                print(f"  처음 들어온 지역 {len(first_seen)}곳은 변경 비교에서 제외")
            print(f"  변경 {prev_dates[-1]} → {args.date}: 추가 {(new_changes['change'] == 'added').sum():,} / "
                  f"삭제 {(new_changes['change'] == 'removed').sum():,}")
        else:
            new_changes = pd.DataFrame(columns=CHANGE_COLS)
            print("  첫 수집 — 비교할 이전 스냅샷 없음")

        scored = score_frame(clean, tables, pd.Timestamp(args.date))
        db.record_snapshot(conn, args.date, sha, len(raw), d1["download_url"])
        db.replace_current(conn, clean)
        db.add_changes(conn, new_changes)
        dates = db.snapshot_dates(conn)
        changes_all = db.load_changes(conn)

        # 배경 통계 원본(data/external)은 git에 없어 CI에서는 비어 있다 → 그때는 DB에 있던 것을 유지
        background, bg_warn = build_background()
        if not background["datasets"]:
            kept = db.get_doc(conn, "background.json")
            if kept and kept.get("datasets"):
                background, bg_warn = kept, ["배경 통계 원본 없음 → DB의 기존 background.json 유지"]

        region_ids = sorted(scored["region_id"].unique())
        a = assemble(scored, region_ids, args.default, mode=mode, snapshot=args.date, snapshot_dates=dates,
                     changes=changes_all, background=background)
        a.warnings[:0] = bg_warn
        n = db.put_docs(conn, validated(B.bundle_docs(**a.docs_kwargs)))
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            size = cur.fetchone()[0]
    print_summary("daily_sync", a, scored, region_ids, limit=5)
    print(f"  DB 저장: 문서 {n:,}개, 스냅샷 {len(dates)}회, DB 크기 {size}, {time.time() - t0:.0f}초")


if __name__ == "__main__":
    main()
