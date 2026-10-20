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


def test_pending_sido_rows_excluded_with_warning():
    import warnings
    from make_mock import fake_rows
    from wifisafe.engine import clean_frame
    raw = fake_rows(6, seed=1)
    raw["설치시도명"] = ["서울특별시"] * 4 + ["전남광주통합특별시"] * 2
    raw["설치시군구명"] = "구로구"
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        df, report = clean_frame(raw)
    assert len(df) == 4 and set(df["region_id"]) == {"11-guro"}
    assert report["excluded_pending_sido"] == {"전남광주통합특별시": 2}
    assert any("전남광주통합특별시" in str(x.message) for x in w)
