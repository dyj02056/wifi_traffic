# [이 테스트가 확인하는 것]
#   칸 이름 대응표와 이름 만들기(wifisafe/schema.py)를 확인한다: 시군구 로마자 슬러그, region_id,
#   지점 고유키가 항상 같게 만들어지는지, 칸 이름이 틀리면 오류가 나는지,
#   시도코드 확인 전 시도는 경고와 함께 빠지는지, 신설 '전남광주통합특별시'가 코드 12를 받는지.
import pytest

from wifisafe.schema import COLUMN_MAP, HeaderMismatch, make_region_id, point_key, sigungu_slug, validate_header


@pytest.mark.parametrize("name,slug", [("구로구", "guro"), ("강남구", "gangnam"), ("중구", "jung"),
                                       ("수원시 장안구", "suwon-jangan"), ("가평군", "gapyeong")])
def test_slug(name, slug):
    assert sigungu_slug(name) == slug


def test_region_id():
    assert make_region_id("서울특별시", "구로구") == "11-guro"


def test_point_key_stable():
    a = point_key(37.4954321, 126.887654, "Public WiFi Free", "OO정류장")
    b = point_key(37.4954319, 126.887654, "Public WiFi Free", "OO정류장")   # 소수 5자리 반올림 동일
    assert a == b and len(a) == 10


def test_header_mismatch_errors():
    with pytest.raises(HeaderMismatch):
        validate_header(["설치장소명", "위도"])
    validate_header(list(COLUMN_MAP) + ["관리번호"])


def test_pending_sido_rows_excluded_with_warning(monkeypatch):
    import warnings
    from make_mock import fake_rows
    from wifisafe import engine
    monkeypatch.setattr(engine, "PENDING_SIDO", {"가상특별시"})
    raw = fake_rows(6, seed=1)
    raw["설치시도명"] = ["서울특별시"] * 4 + ["가상특별시"] * 2
    raw["설치시군구명"] = "구로구"
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        df, report = engine.clean_frame(raw)
    assert len(df) == 4 and set(df["region_id"]) == {"11-guro"}
    assert report["excluded_pending_sido"] == {"가상특별시": 2}
    assert any("가상특별시" in str(x.message) for x in w)


def test_jeonnam_gwangju_special_city_code():
    """행안부 법정동코드 2026-07-01: 전남광주통합특별시 = 12 (requests #37)"""
    from make_mock import fake_rows
    from wifisafe.engine import clean_frame
    raw = fake_rows(2, seed=1)
    raw["설치시도명"] = "전남광주통합특별시"
    raw["설치시군구명"] = ["광산구", "여수시"]
    df, report = clean_frame(raw)
    assert set(df["region_id"].str[:2]) == {"12"} and len(df) == 2
