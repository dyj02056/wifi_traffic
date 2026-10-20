"""GPS 최근접·로그인 API (DB 없이 되는 부분)와 세션 토큰."""
import pytest
from fastapi.testclient import TestClient

from api import session
from api.main import create_app
from wifisafe.io import MOCK_DIR, read_json


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEV_LOGIN", "0")   # backend/.env의 DEV_LOGIN=1과 무관하게 "꺼짐"에서 시작
    return TestClient(create_app(MOCK_DIR))


def test_session_token_roundtrip_tamper_and_expiry(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    t = session.issue(7, now=1_000)
    assert session.verify(t, now=1_001) == 7
    body, sig = t.split(".")
    assert session.verify(f"{body}.{sig[:-2]}AA", now=1_001) is None          # 서명 변조
    assert session.verify(t, now=1_000 + session.TTL_SECONDS + 1) is None      # 만료
    monkeypatch.setenv("SESSION_SECRET", "y" * 32)
    assert session.verify(t, now=1_001) is None                                # 다른 비밀값


def test_session_secret_required(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "short")
    with pytest.raises(RuntimeError):
        session.issue(1)


def test_nearest_without_db_uses_region_center(client):
    r = read_json(MOCK_DIR / "regions.json")
    region = next(x for x in r["regions"] if x["available"])
    c = region["center"]
    res = client.get("/api/nearest", params={"lat": c["lat"], "lng": c["lng"]})
    assert res.status_code == 200
    assert res.json() == {"region_id": region["region_id"], "distance_m": None, "method": "region_center"}


def test_nearest_rejects_outside_korea(client):
    assert client.get("/api/nearest", params={"lat": 51.5, "lng": -0.1}).status_code == 422


def test_member_endpoints_need_db(client, monkeypatch):
    monkeypatch.setenv("DEV_LOGIN", "1")
    assert client.post("/api/auth/dev").status_code == 503
    assert client.get("/api/me", headers={"Authorization": "Bearer x"}).status_code == 503


def test_dev_login_hidden_unless_enabled(client):
    assert client.post("/api/auth/dev").status_code == 404
