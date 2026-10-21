# [이 테스트가 확인하는 것]
#   실제 Neon 데이터베이스와 연결해 저장·조회·가까운 지역 찾기·회원 기능을 확인하는 테스트.
#   평소에는 건너뛰고(skip), TEST_DB=1과 DATABASE_URL이 있을 때만 임시 공간을 만들어 돌린 뒤 지운다.
"""Neon/PostGIS 연동 — TEST_DB=1 이고 DATABASE_URL이 있을 때만, 임시 스키마 안에서 실행하고 지운다.
실행: TEST_DB=1 python -m pytest tests/test_db.py -q
"""
import os
import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from wifisafe import db

pytestmark = pytest.mark.skipif(os.environ.get("TEST_DB") != "1", reason="TEST_DB=1 일 때만 (실제 DB 사용)")


@pytest.fixture(scope="module")
def conn():
    url = db.database_url()
    schema = f"test_{uuid.uuid4().hex[:8]}"
    c = db.connect(url, direct=True)
    with c.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cur.execute(f"CREATE SCHEMA {schema}")
        cur.execute(f"SET search_path TO {schema}, public")
    c.commit()
    db.migrate(c)
    yield c
    c.rollback()
    with c.cursor() as cur:
        cur.execute(f"DROP SCHEMA {schema} CASCADE")
    c.commit()
    c.close()


def _clean(rows):
    return pd.DataFrame([{"key": k, "region_id": r, "sido": "서울특별시", "sigungu": s, "place_name": n, "ssid": "SEOUL",
                          "lat": lat, "lng": lng} for k, r, s, n, lat, lng in rows])


def test_current_nearest_changes_docs_users(conn):
    from wifisafe.changes import diff_snapshots
    a = _clean([("k1", "11-seocho", "서초구", "양재역", 37.4846, 127.0342),
                ("k2", "11-guro", "구로구", "구로역", 37.5030, 126.8820)])
    db.record_snapshot(conn, "2026-10-20", "aaa", 2, "test")
    db.replace_current(conn, a)
    assert sorted(db.load_current(conn)["key"]) == ["k1", "k2"]
    assert db.nearest_region(conn, 37.4837, 127.0324)["region_id"] == "11-seocho"
    assert db.nearest_region(conn, 37.5000, 126.8800)["region_id"] == "11-guro"

    b = _clean([("k1", "11-seocho", "서초구", "양재역", 37.4846, 127.0342),
                ("k3", "11-guro", "구로구", "신도림역", 37.5088, 126.8912)])
    ch = diff_snapshots(db.load_current(conn), b, "2026-10-20", "2026-10-21")
    assert db.add_changes(conn, ch) == 2
    db.record_snapshot(conn, "2026-10-21", "bbb", 2, "test")
    db.replace_current(conn, b)
    assert db.snapshot_dates(conn) == ["2026-10-20", "2026-10-21"]
    assert db.snapshot_by_sha(conn, "bbb") == "2026-10-21"
    assert sorted(db.load_changes(conn)["change"]) == ["added", "removed"]

    db.put_docs(conn, [("meta.json", {"a": 1}), ("points/11-guro.json", {"points": []})])
    db.put_docs(conn, [("meta.json", {"a": 2})])                    # prune: points 문서 삭제
    assert db.get_doc(conn, "meta.json") == {"a": 2}
    assert db.doc_paths(conn) == ["meta.json"]

    u = db.upsert_user(conn, "dev", "local-dev", "개발자")
    assert u["sido"] is None
    assert db.upsert_user(conn, "dev", "local-dev", "개발자2")["id"] == u["id"]   # 같은 계정은 1명
    u2 = db.set_user_region(conn, u["id"], "서울특별시", "서초구", "11-seocho")
    assert u2["region_id"] == "11-seocho" and db.get_user(conn, u["id"])["display_name"] == "개발자2"


def test_api_member_flow_on_db(conn, monkeypatch):
    """DbStore + 개발용 로그인 → 지역 저장 → /api/me (임시 스키마 search_path를 쓰도록 연결을 주입)."""
    from api.main import create_app
    from api.store import DbStore
    monkeypatch.setenv("DEV_LOGIN", "1")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users")       # 앞 테스트가 만든 개발용 회원(지역 저장됨)을 지우고 처음부터
    conn.commit()
    db.put_docs(conn, [("regions.json", {"default_region_id": "11-seocho",
                                         "sido": [{"sido_code": "11", "sido": "서울특별시", "count": 1}],
                                         "regions": [{"region_id": "11-seocho", "sido": "서울특별시", "sigungu": "서초구",
                                                      "available": True, "center": {"lat": 37.48, "lng": 127.03}}]})],
                prune=False)
    store = DbStore("unused")
    store._conn = conn
    app = create_app()
    app.state.store = store
    c = TestClient(app)
    auth = c.post("/api/auth/dev").json()
    assert auth["needs_region"] is True
    h = {"Authorization": f"Bearer {auth['token']}"}
    assert c.put("/api/me/region", json={"region_id": "11-seocho"}, headers=h).json()["sigungu"] == "서초구"
    assert c.get("/api/me", headers=h).json()["region_id"] == "11-seocho"
    assert c.put("/api/me/region", json={"sido_code": "11"}, headers=h).json()["region_id"] is None
    assert c.get("/api/me", headers={"Authorization": "Bearer bad.token"}).status_code == 401
    assert c.get("/api/nearest", params={"lat": 37.4837, "lng": 127.0324}).json()["method"] == "postgis"
