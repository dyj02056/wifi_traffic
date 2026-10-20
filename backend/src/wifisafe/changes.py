"""스냅샷 간 추가·삭제 지점 비교 (plan.md §8.5)."""
from __future__ import annotations

import pandas as pd

CHANGE_COLS = ["snapshot_from", "snapshot_to", "key", "change", "region_id", "sido", "sigungu",
               "place_name", "ssid", "lat", "lng"]


def diff_snapshots(prev: pd.DataFrame, curr: pd.DataFrame, date_from: str, date_to: str) -> pd.DataFrame:
    """prev/curr: clean_frame() 출력. key 기준 비교."""
    pk, ck = set(prev["key"]), set(curr["key"])
    added = curr[curr["key"].isin(ck - pk)].assign(change="added")
    removed = prev[prev["key"].isin(pk - ck)].assign(change="removed")
    out = pd.concat([added, removed], ignore_index=True)
    out["snapshot_from"], out["snapshot_to"] = date_from, date_to
    if out.empty:
        return pd.DataFrame(columns=CHANGE_COLS)
    return out[CHANGE_COLS].sort_values(["snapshot_to", "change", "key"]).reset_index(drop=True)


def to_json(region_id: str, changes: pd.DataFrame, snapshots: list[str]) -> dict:
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
