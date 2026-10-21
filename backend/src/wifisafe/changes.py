"""스냅샷 간 추가·삭제 지점 비교 (plan.md §8.5).

[이 파일이 하는 일]
  공공데이터를 날짜별로 받아 둔 것을 '스냅샷'이라고 부릅니다(그날 찍어 둔 사진 같은 것).
  이전 스냅샷과 이번 스냅샷을 비교해서 새로 생긴 지점(added)과 없어진 지점(removed)을 찾습니다.
  결과는 지도 화면의 '최근 추가·삭제' 레이어에 표시됩니다.

[비교 기준]
  지점마다 붙은 고유키(key)로 비교합니다. 이번에만 있는 키 = 추가, 이전에만 있는 키 = 삭제.
"""
from __future__ import annotations

import pandas as pd

# 변경 기록 표의 칸 목록 (DB의 wifi_changes 테이블과 같은 순서)
CHANGE_COLS = ["snapshot_from", "snapshot_to", "key", "change", "region_id", "sido", "sigungu",
               "place_name", "ssid", "lat", "lng"]


def diff_snapshots(prev: pd.DataFrame, curr: pd.DataFrame, date_from: str, date_to: str) -> pd.DataFrame:
    """prev/curr: clean_frame() 출력. key 기준 비교.

    - prev: 이전 스냅샷(정제된 표), curr: 이번 스냅샷
    - date_from, date_to: 두 스냅샷의 날짜
    """
    pk, ck = set(prev["key"]), set(curr["key"])
    # 집합 빼기: ck - pk = 이번에만 있는 키(추가), pk - ck = 이전에만 있는 키(삭제)
    added = curr[curr["key"].isin(ck - pk)].assign(change="added")
    removed = prev[prev["key"].isin(pk - ck)].assign(change="removed")
    out = pd.concat([added, removed], ignore_index=True)
    out["snapshot_from"], out["snapshot_to"] = date_from, date_to
    if out.empty:
        return pd.DataFrame(columns=CHANGE_COLS)
    return out[CHANGE_COLS].sort_values(["snapshot_to", "change", "key"]).reset_index(drop=True)


def to_json(region_id: str, changes: pd.DataFrame, snapshots: list[str]) -> dict:
    """한 지역의 변경 기록을 changes/<지역>.json 모양으로 만든다."""
    sub = changes[changes["region_id"] == region_id]
    return {
        "region_id": region_id,
        "snapshots": sorted(snapshots),
        "collection_count": len(snapshots),
        "changes": [{
            "key": r.key, "change": r.change, "snapshot_from": r.snapshot_from, "snapshot_to": r.snapshot_to,
            "place_name": r.place_name or None, "ssid": r.ssid or None,
            "lat": round(float(r.lat), 6), "lng": round(float(r.lng), 6),
        } for r in sub.itertuples(index=False)],
    }
