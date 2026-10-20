import pandas as pd
import pytest

from config.rules import PARAMS
from wifisafe import rules as R
from wifisafe.density import r5_density

REF = pd.Timestamp("2026-10-20")
T = R.RuleTables(ssid_labels={"OPEN": "open", "SEC": "secure", "UNK": "unknown"},
                 facility_map={"교통시설": (1.0, "유동인구"), "도서관": (0.25, "실내")},
                 outdoor_keywords=("정류장", "공원"), indoor_override_keywords=("로비",))


def frame(**cols):
    n = max(len(v) for v in cols.values())
    base = {k: [""] * n for k in ("ssid", "facility_type", "place_detail", "install_ym", "provider", "manager",
                                   "manager_tel", "data_date")}
    base.update(cols)
    return pd.DataFrame(base)


def test_r1_labels():
    ratio, _, flag = R.r1_secure_access(frame(ssid=["OPEN", "SEC", "UNK", "NEW"]), T)
    assert ratio.tolist() == [1.0, 0.0, PARAMS["R1_UNKNOWN_RATIO"], PARAMS["R1_UNKNOWN_RATIO"]]
    assert flag.tolist() == ["", "", "R1_unknown", "R1_unlabeled"]


def test_r2_unmapped_flag():
    ratio, reason, flag = R.r2_facility(frame(facility_type=["교통시설", "도서관", "모름"]), T)
    assert ratio.tolist() == [1.0, 0.25, PARAMS["R2_UNMAPPED_RATIO"]]
    assert flag.tolist() == ["", "", "R2_unmapped"]
    assert "유동인구" in reason[0]


def test_r3_outdoor_and_indoor_override():
    ratio, _, _ = R.r3_outdoor(frame(place_detail=["버스정류장", "공원 관리동 로비", "도서관 2층"]), T)
    assert ratio.tolist() == [1.0, 0.0, 0.0]


@pytest.mark.parametrize("ym,expected,flag", [
    ("2026-10", 0.0, ""),            # 0년
    ("2018-10", 1.0, ""),            # 8년 = R4_FULL_YEARS → 1.0
    ("2010-01", 1.0, ""),            # 8년 초과 → 1.0 상한
    ("", PARAMS["R4_MISSING_RATIO"], "R4_missing"),
    ("미상", PARAMS["R4_MISSING_RATIO"], "R4_missing"),
    ("2022", None, "R4_year_only"),
])
def test_r4_age(ym, expected, flag):
    ratio, _, f = R.r4_age(frame(install_ym=[ym]), REF)
    if expected is not None:
        assert ratio[0] == pytest.approx(expected, abs=0.01)
    assert f[0] == flag
    assert 0 <= ratio[0] <= 1


def test_r4_formats():
    for v in ("2017-03", "201703", "2017.03", "2017/03"):
        ts, year_only = R.parse_install_ym(v)
        assert (ts.year, ts.month, year_only) == (2017, 3, False)


@pytest.mark.parametrize("days,expected", [(0, 0.0), (179, 0.0), (180, 0.5), (364, 0.5), (365, 1.0), (900, 1.0)])
def test_r8_boundaries(days, expected):
    d = (REF - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    ratio, _, _ = R.r8_data_age(frame(data_date=[d]), REF)
    assert ratio[0] == expected


def test_r8_missing():
    ratio, _, flag = R.r8_data_age(frame(data_date=["2026-10-18", "", "20261018"]), REF)
    assert ratio.tolist() == [0.0, 1.0, 0.0]          # 결측이 앞 값으로 채워지지 않아야 함
    assert flag.tolist() == ["", "R8_missing", ""]


@pytest.mark.parametrize("tel,expected", [
    ("02-000-0000", 0.0), ("031-1234-5678", 0.0), ("010-1234-5678", 0.0), ("1588-1234", 0.0),
    ("(02) 123 4567", 0.0), ("", 1.0), ("000", 1.0), ("02-12", 1.0), ("없음", 1.0),
])
def test_r7_tel(tel, expected):
    ratio, _, _ = R.r7_report_path(frame(manager_tel=[tel]))
    assert ratio[0] == expected


def test_r6_operator():
    ratio, _, _ = R.r6_operator(frame(provider=["KT", "", "미상", "기타"], manager=["구청", "구청", "", "기타"]))
    assert ratio.tolist() == [0.0, PARAMS["R6_PARTIAL_RATIO"], 1.0, 1.0]


def test_r5_density_excludes_self_and_flags_boundary():
    # A 지역에 개방형 3개가 한 점에, B 지역에 개방형 1개가 바로 옆(같은 좌표)
    df = pd.DataFrame({"region_id": ["11-a"] * 3 + ["11-b"], "lat": [37.5] * 4, "lng": [127.0] * 4})
    ratio, _, flag, cnt = r5_density(df, pd.Series([True, True, True, True]))
    assert cnt.tolist() == [2, 2, 2, 0]                       # 자신 제외, 같은 시군구만
    assert ratio[0] == pytest.approx(2 / PARAMS["R5_FULL_COUNT"])
    assert flag.tolist() == ["R5_boundary"] * 4               # 이웃 시군구 AP가 반경 안에 있음


def test_r5_far_points_not_counted():
    df = pd.DataFrame({"region_id": ["11-a", "11-a"], "lat": [37.5, 37.51], "lng": [127.0, 127.0]})  # ~1.1km
    _, _, flag, cnt = r5_density(df, pd.Series([True, True]))
    assert cnt.tolist() == [0, 0] and flag.tolist() == ["", ""]


def test_score_frame_r_in_range():
    from make_mock import MOCK_TABLES, fake_rows
    from wifisafe.engine import clean_frame, score_frame
    df, _ = clean_frame(fake_rows(30, seed=7), mock=True)
    s = score_frame(df, MOCK_TABLES, REF)
    rc = [f"r{i}" for i in range(1, 9)]
    assert ((s[rc] >= 0) & (s[rc] <= 1)).all().all()
    assert s["score"].between(0, 100).all()


def test_r1_empty_ssid_is_unknown_with_flag():
    ratio, reason, flag = R.r1_secure_access(frame(ssid=["", "OPEN"]), T)
    assert ratio.tolist() == [PARAMS["R1_UNKNOWN_RATIO"], 1.0]
    assert flag.tolist() == ["R1_ssid_missing", ""]


def test_r1_region_status_coverage_threshold():
    from wifisafe.engine import enforce_r1_region_gate, r1_region_status
    # a: 10행 중 9행 확정(90%) → confirmed, b: 10행 중 8행(80%) → provisional, c: SSID 전부 빈 값 → no_ssid
    # 빈 SSID 행은 분모에서 빠진다(a의 빈 행 2개)
    df = pd.DataFrame({"region_id": ["a"] * 12 + ["b"] * 10 + ["c"] * 3,
                       "ssid": ["OK"] * 9 + ["NEW"] + ["", None] + ["OK"] * 8 + ["NEW"] * 2 + ["", " ", None]})
    st = r1_region_status(df, {"OK"})
    assert st == {"a": ("confirmed", 0.9), "b": ("provisional", 0.8), "c": ("no_ssid", None)}
    enforce_r1_region_gate("final", st, ["a", "c"])          # provisional 지역이 없으면 통과
    enforce_r1_region_gate("dev", st, ["b"])                 # dev는 막지 않음
    with pytest.raises(SystemExit, match="b"):
        enforce_r1_region_gate("final", st, ["a", "b"])
