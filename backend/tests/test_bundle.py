# [이 테스트가 확인하는 것]
#   만들어진 번들(mock, 그리고 있으면 실데이터)이 contracts/ 스키마를 지키는지, 안내 문구가 들어 있는지,
#   key_index가 지점 목록과 맞는지, 데이터 있음(available) 지역마다 파일이 다 있는지,
#   사례 카드에 출처·날짜가 빠지면 오류가 나는지 확인한다.
import pytest

from config.rules import DISCLAIMER
from wifisafe.cases import CaseSourceError, load_cases
from wifisafe.io import DIST_DATA_DIR, MOCK_DIR, read_json, validate_bundle

BUNDLES = [MOCK_DIR] + ([DIST_DATA_DIR] if (DIST_DATA_DIR / "meta.json").exists() else [])


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_bundle_schema_valid(bundle):
    assert validate_bundle(bundle) == []


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_meta_disclaimer(bundle):
    assert read_json(bundle / "meta.json")["disclaimer"] == DISCLAIMER


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_key_index_matches_points(bundle):
    idx = read_json(bundle / "key_index.json")
    from_points = {}
    for p in (bundle / "points").glob("*.json"):
        pj = read_json(p)
        assert pj["count"] == len(pj["points"])
        for pt in pj["points"]:
            assert pt["key"] not in from_points, "key 중복"
            from_points[pt["key"]] = pj["region_id"]
    assert idx == from_points
    for p in (bundle / "detail").glob("*.json"):
        assert set(read_json(p)) == {k for k, r in idx.items() if r == p.stem}


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_regions_available_have_files(bundle):
    regions = read_json(bundle / "regions.json")
    avail = {r["region_id"] for r in regions["regions"] if r["available"]}
    assert regions["default_region_id"] in avail
    for folder in ("points", "detail", "changes", "sensitivity"):
        assert {p.stem for p in (bundle / folder).glob("*.json")} == avail


def test_mock_flag():
    assert read_json(MOCK_DIR / "meta.json")["is_mock"] is True


def test_case_without_source_errors(tmp_path):
    p = tmp_path / "cases.yaml"
    p.write_text("cases:\n  - id: x\n    title: t\n    summary: s\n    principle: p\n    source:\n      name: 언론\n",
                 encoding="utf-8")
    with pytest.raises(CaseSourceError):
        load_cases(p)


def test_case_with_source_ok(tmp_path):
    p = tmp_path / "cases.yaml"
    p.write_text("cases:\n  - id: x\n    title: t\n    summary: s\n    principle: p\n    related_rules: [R1]\n"
                 "    source:\n      name: 언론\n      url: https://example.com/a\n      published_at: 2026-08-09\n"
                 "      retrieved_at: 2026-10-20\n", encoding="utf-8")
    assert load_cases(p)["cases"][0]["source"]["published_at"] == "2026-08-09"
