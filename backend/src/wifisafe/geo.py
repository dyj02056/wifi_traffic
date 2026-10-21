"""좌표 이상 처리 (docs/requests.md #32). 원본 좌표는 고치거나 지우지 않는다(규칙 1) — 지도 보기만 바로잡는다.

[이 파일이 하는 일]
  공공데이터에는 엉뚱한 곳에 찍힌 좌표(예: 고양시 지점인데 부산에 찍힘)가 섞여 있습니다.
  이런 점 때문에 지도를 열었을 때 화면이 전국으로 확 펼쳐지지 않도록, 지역마다 '보기 좋은 화면 범위'를 계산하고,
  수상한 좌표에는 표시(COORD_suspect)만 붙입니다. 점수·등급은 바꾸지 않습니다.

[용어 풀이]
  - bbox(bounding box): 지점들을 모두 감싸는 네모 범위. [최소 경도, 최소 위도, 최대 경도, 최대 위도] 순서.
  - 분위수(quantile): 값을 작은 순으로 줄 세웠을 때 특정 비율 위치의 값. 0.01 분위수 = 아래에서 1% 지점의 값.
  - 중앙값(median): 줄 세웠을 때 한가운데 값. 평균과 달리 동떨어진 값의 영향을 덜 받는다.

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
# 참고: 위도 1도 ≈ 111km. 경도 1도는 위도가 높을수록 짧아져서 111km × cos(위도)로 계산한다(아래 코드의 111).


def robust_bbox(lat: pd.Series, lng: pd.Series) -> list[float]:
    """[minLng, minLat, maxLng, maxLat] — 바깥 2%를 뺀 범위.

    가장 작은 1%와 가장 큰 1%를 무시하고 범위를 잡아서, 동떨어진 몇 개 점에 휘둘리지 않게 한다.
    """
    return [round(float(lng.quantile(TRIM)), 6), round(float(lat.quantile(TRIM)), 6),
            round(float(lng.quantile(1 - TRIM)), 6), round(float(lat.quantile(1 - TRIM)), 6)]


def line_pattern(lat: pd.Series, lng: pd.Series) -> pd.Series:
    """한 지역 안에서 같은 간격(LINE_MIN_STEP_KM 이상)으로 LINE_MIN_POINTS곳 이상 일직선으로 이어진 좌표면 True.

    원본 데이터 중에는 좌표를 일정 간격씩 기계적으로 늘려 입력한 오류가 있다(점들이 자로 그은 듯 한 줄로 늘어섬).
    방법: ① 좌표를 정수로 바꿔 정렬하고 ② 이웃한 점 사이의 '이동 간격'이 몇 번 나오는지 센 뒤
          ③ 자주 나오는 간격으로 점을 이어 따라가서 8곳 이상 이어지는 '사슬'을 찾는다.
    """
    # 소수점 비교 오차를 피하려고 좌표에 100만을 곱해 정수로 바꾼다. 예) 37.123456 → 37123456
    q = list(zip((lat * 1e6).round().astype("int64"), (lng * 1e6).round().astype("int64")))
    pts = set(q)
    arr = sorted(pts)
    # 정렬된 이웃 점끼리의 (위도 차, 경도 차)를 모아 가장 많이 나온 순서로 센다.
    steps = pd.Series([(b[0] - a[0], b[1] - a[1]) for a, b in zip(arr, arr[1:])], dtype=object).value_counts()
    bad: set = set()
    for (dy, dx), cnt in steps.items():
        if cnt < LINE_MIN_POINTS - 1:
            break                               # 많이 나온 순서로 보므로, 이보다 적으면 뒤는 볼 필요 없음
        # 간격이 너무 짧으면(0.3km 미만) 정상 데이터일 수 있으므로 건너뛴다.
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
    clat, clng = float(la.median()), float(ln.median())   # 지점들의 중심
    # 중심에서 각 지점까지의 거리(km)를 피타고라스 공식으로 근사 계산한다(가까운 거리라 충분히 정확).
    d = ((ln - clng) * 111 * math.cos(math.radians(clat))) ** 2 + ((la - clat) * 111) ** 2
    d = d ** 0.5
    core = d <= max(VIEW_MIN_KM, VIEW_K * float(d.quantile(0.75)))
    return robust_bbox(la[core], ln[core])


def coord_suspects(df: pd.DataFrame) -> pd.Series:
    """일직선 이상 좌표이거나, _trim_bbox에서 (폭×PAD_RATIO, 최소 PAD_MIN_DEG)보다 더 벗어난 지점이면 True.

    지역(region_id)마다 따로 판정한다. '|'는 '또는'이라는 뜻.
    """
    out = pd.Series(False, index=df.index)
    for _, g in df.groupby("region_id"):
        line = line_pattern(g["lat"], g["lng"])
        w, s, e, n = _trim_bbox(g["lat"], g["lng"])   # 서·남·동·북 경계
        pad_lng = max(PAD_MIN_DEG, (e - w) * PAD_RATIO)
        pad_lat = max(PAD_MIN_DEG, (n - s) * PAD_RATIO)
        out.loc[g.index] = (line | (g["lng"] < w - pad_lng) | (g["lng"] > e + pad_lng)
                            | (g["lat"] < s - pad_lat) | (g["lat"] > n + pad_lat))
    return out
