# [이 테스트가 확인하는 것]
#   API 서버가 mock 번들을 그대로 내주는지 확인한다: 주소별 응답 모양, 없는 지역·지점은 404,
#   모든 응답에 안내 문구 머리말(X-Disclaimer)이 붙는지, /explain이 템플릿 설명을 돌려주는지 등.
#   TestClient: 실제 서버를 띄우지 않고 API에 요청을 보내 볼 수 있는 테스트 도구.
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from config.rules import DISCLAIMER
from wifisafe.io import MOCK_DIR, read_json


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(MOCK_DIR))


@pytest.fixture(scope="module")
def region_id():
    return read_json(MOCK_DIR / "regions.json")["default_region_id"]


def test_point_detail_ok(client):
    key = next(iter(read_json(MOCK_DIR / "key_index.json")))
    r = client.get(f"/api/points/{key}")
    assert r.status_code == 200
    assert r.json()["key"] == key


def test_point_unknown_404(client):
    assert client.get("/api/points/ffffffffff").status_code == 404


def test_all_endpoints(client, region_id):
    for path in ("/api/meta", "/api/rules", "/api/regions", f"/api/regions/{region_id}/points",
                 f"/api/regions/{region_id}/changes", f"/api/regions/{region_id}/sensitivity", "/api/background",
                 "/api/cases"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert urllib.parse.unquote(r.headers["X-Disclaimer"]) == DISCLAIMER


def test_api_equals_bundle(client, region_id):
    assert client.get(f"/api/regions/{region_id}/points").json() == read_json(MOCK_DIR / "points" / f"{region_id}.json")


def test_unknown_region_404(client):
    assert client.get("/api/regions/99-nowhere/points").status_code == 404
    assert client.get("/api/regions/..%2F..%2Fmeta/points").status_code == 404


def test_explain_template_without_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    key = next(iter(read_json(MOCK_DIR / "key_index.json")))
    r = client.post(f"/api/points/{key}/explain")
    assert r.status_code == 200
    body = r.json()
    assert body["ai_available"] is False and body["explanation"]["source"] == "template"
