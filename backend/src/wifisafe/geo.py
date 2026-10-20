"""좌표 이상 처리 (docs/requests.md #32). 원본 좌표는 고치거나 지우지 않는다(규칙 1) — 지도 보기만 바로잡는다.

- 지역의 지도 범위(bbox)는 위·경도 각각 양쪽 1%씩(바깥 2%)을 빼고 잡는다 → 동떨어진 한두 점 때문에 지도가 전국으로 펼쳐지지 않게
- 처음 화면 범위(regions.json bbox)는 그와 별개로 지점이 몰린 중심부로 잡는다(view_bbox, #38)
- 그 범위에서 크게 벗어난 지점에는 COORD_suspect 표시만 붙인다(점수·등급은 그대로)
- 같은 간격으로 일직선으로 이어진 좌표(번호를 붙여 기계적으로 늘린 원본 오류, 대전 서구 302곳)도
  COORD_suspect로 표시하고 범위 계산에서 뺀다 (#38). 바깥 2% 제외만으로는 30%나 되는 이런 점을 못 거른다
"""
from __future__ import annotations

import math

import pandas as pd

TRIM = 0.01            # 양쪽 1%씩
PAD_RATIO = 0.5        # 범위 폭의 50%까지는 정상으로 본다
PAD_MIN_DEG = 0.02     # 범위가 아주 좁은 지역도 최소 약 2km 여유
SUSPECT_FLAG = "COORD_suspect"
LINE_MIN_POINTS = 8     # 같은 간격으로 8곳 이상 이어지면
LINE_MIN_STEP_KM = 0.3  # 간격이 0.3km 이상일 때만 (좌표를 소수 셋째 자리로 반올림한 정상 데이터 제외)
VIEW_K = 3.0            # 처음 화면: 중심(중앙값)에서 '75% 지점까지 거리'의 3배 안쪽만
VIEW_MIN_KM = 5.0       # 최소 5km


def robust_bbox(lat: pd.Series, lng: pd.Series) -> list[float]:
    """[minLng, minLat, maxLng, maxLat] — 바깥 2%를 뺀 범위."""
    return [round(float(lng.quantile(TRIM)), 6), round(float(lat.quantile(TRIM)), 6),
            round(float(lng.quantile(1 - TRIM)), 6), round(float(lat.quantile(1 - TRIM)), 6)]


def line_pattern(lat: pd.Series, lng: pd.Series) -> pd.Series:
    """한 지역 안에서 같은 간격(LINE_MIN_STEP_KM 이상)으로 LINE_MIN_POINTS곳 이상 일직선으로 이어진 좌표면 True."""
    q = list(zip((lat * 1e6).round().astype("int64"), (lng * 1e6).round().astype("int64")))
    pts = set(q)
    arr = sorted(pts)
    steps = pd.Series([(b[0] - a[0], b[1] - a[1]) for a, b in zip(arr, arr[1:])], dtype=object).value_counts()
    bad: set = set()
    for (dy, dx), cnt in steps.items():
        if cnt < LINE_MIN_POINTS - 1:
            break
        if math.hypot(dy / 1e6 * 111, dx / 1e6 * 111 * math.cos(math.radians(arr[0][0] / 1e6))) < LINE_MIN_STEP_KM:
            continue
        for p in pts:
            if (p[0] - dy, p[1] - dx) in pts:
                continue                        # 사슬의 첫 점에서만 출발
            chain = [p]
            while (chain[-1][0] + dy, chain[-1][1] + dx) in pts:
                chain.append((chain[-1][0] + dy, chain[-1][1] + dx))
            if len(chain) >= LINE_MIN_POINTS:
                bad.update(chain)
    return pd.Series([p in bad for p in q], index=lat.index)


def _trim_bbox(lat: pd.Series, lng: pd.Series) -> list[float]:
    """일직선 이상 좌표를 뺀 뒤 robust_bbox (COORD_suspect 판정 기준). 전부 걸리면 원래 값으로."""
    keep = ~line_pattern(lat, lng)
    return robust_bbox(lat[keep], lng[keep]) if keep.any() else robust_bbox(lat, lng)


def view_bbox(lat: pd.Series, lng: pd.Series) -> list[float]:
    """regions.json bbox = 지역을 처음 열 때 화면에 꽉 차게 보여 줄 범위.
    일직선 이상 좌표를 빼고, 지점이 몰린 중심부(중앙값에서 VIEW_K×75% 거리, 최소 VIEW_MIN_KM)만으로 잡는다.
    지점은 모두 지도에 그려지고, 범위 밖 지점은 축소하면 보인다(전국 지역 중앙값 약 5%)."""
    keep = ~line_pattern(lat, lng)
    if not keep.any():
        return robust_bbox(lat, lng)
    la, ln = lat[keep], lng[keep]
    clat, clng = float(la.median()), float(ln.median())
    d = ((ln - clng) * 111 * math.cos(math.radians(clat))) ** 2 + ((la - clat) * 111) ** 2
    d = d ** 0.5
    core = d <= max(VIEW_MIN_KM, VIEW_K * float(d.quantile(0.75)))
    return robust_bbox(la[core], ln[core])


def coord_suspects(df: pd.DataFrame) -> pd.Series:
    """일직선 이상 좌표이거나, _trim_bbox에서 (폭×PAD_RATIO, 최소 PAD_MIN_DEG)보다 더 벗어난 지점이면 True."""
    out = pd.Series(False, index=df.index)
    for _, g in df.groupby("region_id"):
        line = line_pattern(g["lat"], g["lng"])
        w, s, e, n = _trim_bbox(g["lat"], g["lng"])
        pad_lng = max(PAD_MIN_DEG, (e - w) * PAD_RATIO)
        pad_lat = max(PAD_MIN_DEG, (n - s) * PAD_RATIO)
        out.loc[g.index] = (line | (g["lng"] < w - pad_lng) | (g["lng"] > e + pad_lng)
                            | (g["lat"] < s - pad_lat) | (g["lat"] > n + pad_lat))
    return out
