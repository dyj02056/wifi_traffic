"""스냅샷 목록·로드 공용 헬퍼 (pipeline 스크립트끼리 공유)."""
import _bootstrap  # noqa: F401
import pandas as pd

from wifisafe.io import MANIFEST_PATH, SNAPSHOT_DIR, read_csv_any


def snapshot_dates() -> list[str]:
    if not MANIFEST_PATH.exists():
        return []
    m = pd.read_csv(MANIFEST_PATH, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return sorted(m["snapshot_date"].tolist())


def resolve(date: str | None) -> str:
    dates = snapshot_dates()
    if not dates:
        raise SystemExit("등록된 스냅샷이 없습니다. 먼저 python pipeline/ingest_snapshot.py <CSV> 를 실행하세요")
    if date is None:
        return dates[-1]
    if date not in dates:
        raise SystemExit(f"스냅샷 {date} 없음. 등록된 날짜: {dates}")
    return date


def load_raw(date: str) -> pd.DataFrame:
    df, _ = read_csv_any(SNAPSHOT_DIR / f"{date}.csv")
    return df
