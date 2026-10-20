import pandas as pd

from wifisafe.geo import SUSPECT_FLAG, coord_suspects, robust_bbox


def _region(n=200, rid="11-seocho"):
    # 서초구 근처 격자 + 동해 바다에 찍힌 1점(실제 원본 사례: 서초구민체육센터 39.4988, 128.9905)
    # 불규칙하게 흩어진 점(정확한 격자는 일직선 패턴으로 잡히므로 피함)
    lat = [37.45 + (i * 7919 % 997) / 997 * 0.06 for i in range(n)] + [39.4988]
    lng = [126.98 + (i * 104729 % 991) / 991 * 0.06 for i in range(n)] + [128.9905]
    return pd.DataFrame({"region_id": rid, "lat": lat, "lng": lng})


def test_robust_bbox_ignores_far_outlier():
    df = _region()
    w, s, e, n = robust_bbox(df["lat"], df["lng"])
    assert n < 37.6 and e < 127.1          # 바다의 한 점 때문에 범위가 늘어나지 않음
    assert w >= 126.98 and s >= 37.45


def test_coord_suspects_flags_only_the_outlier_per_region():
    df = pd.concat([_region(), _region(rid="11-guro").assign(lat=lambda d: d.lat + 0.05)], ignore_index=True)
    sus = coord_suspects(df)
    assert sus.sum() == 2                      # 지역마다 바다의 1점만
    assert set(df.loc[sus, "lat"].round(4)) == {39.4988, 39.5488}
    assert SUSPECT_FLAG == "COORD_suspect"


def test_line_pattern_flagged_and_excluded_from_bbox():
    # 대전 서구 원본 사례: 같은 간격(위도 +0.008138, 경도 -0.014252)으로 서해까지 이어진 좌표
    from wifisafe.geo import line_pattern, view_bbox
    df = _region(rid="30-seo")
    line = pd.DataFrame({"region_id": "30-seo", "lat": [36.40 + 0.008138 * i for i in range(30)],
                         "lng": [127.30 - 0.014252 * i for i in range(30)]})
    df = pd.concat([df, line], ignore_index=True)
    m = line_pattern(df["lat"], df["lng"])
    assert m.sum() == 30
    w, s, e, n = view_bbox(df["lat"], df["lng"])
    assert w >= 126.98 and n < 37.6               # 사슬 때문에 범위가 늘어나지 않음
    assert coord_suspects(df)[m].all()


def test_rounded_grid_is_not_line_pattern():
    # 좌표를 소수 셋째 자리로 반올림한 정상 데이터(송파구 등): 0.001도 간격 격자는 걸리지 않음
    from wifisafe.geo import line_pattern
    lat = pd.Series([37.500 + 0.001 * (i % 10) for i in range(100)])
    lng = pd.Series([127.090 + 0.001 * (i // 10) for i in range(100)])
    assert not line_pattern(lat, lng).any()


def test_view_bbox_ignores_few_far_points():
    # 대전 서구 원본 사례: 일직선 오류를 빼고도 청주·세종 쪽에 4곳(8행)이 남음 → 처음 화면은 중심부만
    from wifisafe.geo import view_bbox
    df = _region()
    far = pd.DataFrame({"lat": [36.94, 36.94, 36.65, 36.65, 37.0, 37.0, 37.1, 37.1],
                        "lng": [127.48, 127.48, 127.70, 127.70, 127.5, 127.5, 127.6, 127.6]})
    lat = pd.concat([df["lat"], far["lat"]], ignore_index=True)
    lng = pd.concat([df["lng"], far["lng"]], ignore_index=True)
    w, s, e, n = view_bbox(lat, lng)
    assert s >= 37.45 and n <= 37.52 and w >= 126.98 and e <= 127.05
