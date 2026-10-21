"""스냅샷 목록·로드 공용 헬퍼 (pipeline 스크립트끼리 공유).

[이 파일이 하는 일]
  data/raw/snapshots/에 날짜별로 보관된 원본 CSV(스냅샷)를 찾고 읽는 작은 도구 모음입니다.
"""
import _bootstrap  # noqa: F401
import pandas as pd

from wifisafe.io import MANIFEST_PATH, SNAPSHOT_DIR, read_csv_any


def snapshot_dates() -> list[str]:
    """등록된 스냅샷 날짜 목록(오래된 순). manifest.csv가 없으면 빈 목록."""
    if not MANIFEST_PATH.exists():
        return []
    m = pd.read_csv(MANIFEST_PATH, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return sorted(m["snapshot_date"].tolist())


def resolve(date: str | None) -> str:
    """날짜를 확인한다. None이면 가장 최근 스냅샷 날짜를, 없는 날짜면 등록된 날짜를 알려 주며 멈춘다."""
    dates = snapshot_dates()
    if not dates:
        raise SystemExit("등록된 스냅샷이 없습니다. 먼저 python pipeline/ingest_snapshot.py <CSV> 를 실행하세요")
    if date is None:
        return dates[-1]
    if date not in dates:
        raise SystemExit(f"스냅샷 {date} 없음. 등록된 날짜: {dates}")
    return date


def load_raw(date: str) -> pd.DataFrame:
    """그 날짜의 원본 CSV를 표로 읽는다(인코딩 자동 판별)."""
    df, _ = read_csv_any(SNAPSHOT_DIR / f"{date}.csv")
    return df
