"""R5 개방형 AP 밀집도 — 같은 시군구 내 반경 R5_RADIUS_M 안의 개방형 AP 수(자신 제외).

[이 파일이 하는 일]
  지점마다 "내 주변 100m 안에 비밀번호 없는(개방형) 와이파이가 몇 개 있나"를 셉니다.
  개방형 와이파이가 많이 몰린 곳일수록 해커가 진짜처럼 꾸민 '가짜 와이파이'를 섞어 두기 쉽다고 보기 때문입니다.
  5개(R5_FULL_COUNT) 이상이면 위험비율 1.0, 0개면 0.0, 그 사이는 개수 ÷ 5.

[거리 계산 방법]
  지구는 둥글어서 위도·경도 차이를 그냥 빼면 거리가 정확하지 않습니다.
  그래서 '하버사인(haversine)' 공식(구 위의 두 점 사이 거리 공식)을 쓰고,
  수만 개 지점을 빠르게 세기 위해 BallTree라는 '공간 검색용 자료구조'를 씁니다.

시군구 경계 한계: 이웃 시군구 AP는 세지 않으므로 경계 근처 지점은 과소평가될 수 있다.
전국 데이터로 '이웃 시군구 개방형 AP가 반경 안에 있는' 지점을 찾아 R5_boundary flag를 단다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from config.rules import PARAMS

# 지구 평균 반지름(미터). 미터 단위 반경을 하버사인 계산용 '각도'로 바꿀 때 쓴다.
EARTH_RADIUS_M = 6_371_008.8


def _counts(tree_pts: np.ndarray, query_pts: np.ndarray, radius_m: float) -> np.ndarray:
    """query_pts의 각 점마다, 반경 radius_m 안에 tree_pts가 몇 개 있는지 센다.

    좌표는 [위도, 경도] 쌍의 목록. 하버사인 계산은 각도를 라디안 단위로 받아서 np.radians로 바꿔 넣는다.
    """
    if len(tree_pts) == 0 or len(query_pts) == 0:
        return np.zeros(len(query_pts), dtype=int)
    tree = BallTree(np.radians(tree_pts), metric="haversine")
    return tree.query_radius(np.radians(query_pts), r=radius_m / EARTH_RADIUS_M, count_only=True).astype(int)


def r5_density(df: pd.DataFrame, is_open: pd.Series):
    """df: region_id, lat, lng 컬럼. is_open: R1 라벨이 open인지(bool).

    돌려주는 값: (위험비율, 이유, flag, 같은 시군구 기준 개방형 AP 개수) 네 Series
    """
    radius = PARAMS["R5_RADIUS_M"]
    full = PARAMS["R5_FULL_COUNT"]
    coords = df[["lat", "lng"]].to_numpy(dtype=float)
    open_mask = is_open.to_numpy(dtype=bool)

    # 1) 같은 시군구 안에서만 센 개수 (점수에 쓰는 값)
    same = np.zeros(len(df), dtype=int)
    for _, idx in df.groupby("region_id").indices.items():
        idx = np.asarray(idx)
        open_idx = idx[open_mask[idx]]
        same[idx] = _counts(coords[open_idx], coords[idx], radius)
    same = same - open_mask.astype(int)          # 자기 자신 제외 (내가 개방형이면 나도 세어졌으므로 1을 뺀다)
    # 2) 시군구 구분 없이 전국에서 센 개수 (경계 표시용)
    total = _counts(coords[open_mask], coords, radius) - open_mask.astype(int)

    ratio = np.clip(same / full, 0.0, 1.0)
    reason = [f"반경 {radius}m 안 개방형 AP {n}개(같은 시군구 기준)" for n in same]
    # 전국 개수가 더 많다 = 이웃 시군구 AP가 반경 안에 있다 → 점수는 그대로 두고 표시만 붙인다.
    flag = np.where(total > same, "R5_boundary", "")
    return (pd.Series(ratio, index=df.index, dtype=float), pd.Series(reason, index=df.index),
            pd.Series(flag, index=df.index), pd.Series(same, index=df.index))
