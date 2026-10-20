"""R5 개방형 AP 밀집도 — 같은 시군구 내 반경 R5_RADIUS_M 안의 개방형 AP 수(자신 제외).

시군구 경계 한계: 이웃 시군구 AP는 세지 않으므로 경계 근처 지점은 과소평가될 수 있다.
전국 데이터로 '이웃 시군구 개방형 AP가 반경 안에 있는' 지점을 찾아 R5_boundary flag를 단다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from config.rules import PARAMS

EARTH_RADIUS_M = 6_371_008.8


def _counts(tree_pts: np.ndarray, query_pts: np.ndarray, radius_m: float) -> np.ndarray:
    if len(tree_pts) == 0 or len(query_pts) == 0:
        return np.zeros(len(query_pts), dtype=int)
    tree = BallTree(np.radians(tree_pts), metric="haversine")
    return tree.query_radius(np.radians(query_pts), r=radius_m / EARTH_RADIUS_M, count_only=True).astype(int)


def r5_density(df: pd.DataFrame, is_open: pd.Series):
    """df: region_id, lat, lng 컬럼. is_open: R1 라벨이 open인지(bool)."""
    radius = PARAMS["R5_RADIUS_M"]
    full = PARAMS["R5_FULL_COUNT"]
    coords = df[["lat", "lng"]].to_numpy(dtype=float)
    open_mask = is_open.to_numpy(dtype=bool)

    same = np.zeros(len(df), dtype=int)
    for _, idx in df.groupby("region_id").indices.items():
        idx = np.asarray(idx)
        open_idx = idx[open_mask[idx]]
        same[idx] = _counts(coords[open_idx], coords[idx], radius)
    same = same - open_mask.astype(int)          # 자기 자신 제외
    total = _counts(coords[open_mask], coords, radius) - open_mask.astype(int)

    ratio = np.clip(same / full, 0.0, 1.0)
    reason = [f"반경 {radius}m 안 개방형 AP {n}개(같은 시군구 기준)" for n in same]
    flag = np.where(total > same, "R5_boundary", "")
    return (pd.Series(ratio, index=df.index, dtype=float), pd.Series(reason, index=df.index),
            pd.Series(flag, index=df.index), pd.Series(same, index=df.index))
