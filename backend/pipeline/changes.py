"""스냅샷 간 추가·삭제 이력 → processed/wifi_changes.csv (plan.md §8.5)

[이 파일이 하는 일]
  날짜별로 받아 둔 원본 데이터(스냅샷)를 모두 정제한 뒤, 날짜순으로 이웃한 두 개씩 비교해
  새로 생긴 지점과 사라진 지점 목록을 만듭니다. (예: 10-20 vs 10-21, 10-21 vs 10-22 …)
  비교 방법 자체는 src/wifisafe/changes.py에 있습니다. 결과는 export_bundle.py가 번들에 넣습니다.

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
    # prev에는 바로 앞 스냅샷의 (날짜, 정제된 표)를 들고 다니며 이번 것과 비교한다
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
