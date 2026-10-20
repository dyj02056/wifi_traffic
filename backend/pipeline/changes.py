"""스냅샷 간 추가·삭제 이력 → processed/wifi_changes.csv (plan.md §8.5)

등록된 모든 스냅샷을 날짜순으로 이웃끼리 비교한다.
실행: python pipeline/changes.py
"""
import _bootstrap  # noqa: F401
import pandas as pd

from snapshots import load_raw, snapshot_dates
from wifisafe.changes import CHANGE_COLS, diff_snapshots
from wifisafe.engine import clean_frame
from wifisafe.io import PROCESSED_DIR, write_csv


def main():
    dates = snapshot_dates()
    out = PROCESSED_DIR / "wifi_changes.csv"
    if len(dates) < 2:
        write_csv(out, pd.DataFrame(columns=CHANGE_COLS))
        print(f"[changes] 스냅샷 {len(dates)}회 — 비교하려면 2회 이상 필요. 빈 파일 생성: {out}")
        return
    frames, prev = [], None
    for d in dates:
        cur, _ = clean_frame(load_raw(d))
        if prev is not None:
            ch = diff_snapshots(prev[1], cur, prev[0], d)
            print(f"  {prev[0]} → {d}: 추가 {(ch['change'] == 'added').sum()}, 삭제 {(ch['change'] == 'removed').sum()}")
            frames.append(ch)
        prev = (d, cur)
    allch = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CHANGE_COLS)
    write_csv(out, allch)
    print(f"[changes] {len(dates)}회 수집, 기간 {dates[0]} ~ {dates[-1]}, 변경 {len(allch)}건 → {out}")


if __name__ == "__main__":
    main()
