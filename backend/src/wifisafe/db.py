"""Neon(Postgres + PostGIS) 접근 (docs/requests.md #15·#18·#19).

API(Vercel)도 이 모듈을 쓰므로 pandas는 pipeline 전용 함수 안에서만 import한다.
연결 정보는 환경변수 DATABASE_URL(backend/.env 또는 GitHub Secrets·Vercel 환경변수)에서만 읽는다.
"""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Iterable

from wifisafe.io import BACKEND_DIR, load_env

if TYPE_CHECKING:
    import pandas as pd
    import psycopg

SCHEMA_SQL = BACKEND_DIR / "db" / "schema.sql"
CURRENT_COLS = ["key", "region_id", "sido", "sigungu", "place_name", "ssid", "lat", "lng"]


def database_url(required: bool = True) -> str | None:
    load_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url and required:
        raise SystemExit("DATABASE_URL이 없습니다. backend/.env에 Neon 연결 문자열을 넣으세요(채팅·코드에 쓰지 말 것).")
    return url or None


def direct_url(url: str) -> str:
    """Neon 풀러 주소(ep-xxx-pooler.…)를 직접 연결 주소(ep-xxx.…)로. 긴 트랜잭션·대량 저장(daily_sync)은 직접 연결이 안전하다."""
    return url.replace("-pooler.", ".", 1)


def connect(url: str | None = None, direct: bool = False) -> "psycopg.Connection":
    """API는 풀러 주소 그대로, pipeline(direct=True)은 직접 연결. 풀러에서도 동작하도록 서버측 prepared statement는 끈다."""
    import psycopg
    url = url or database_url()
    return psycopg.connect(direct_url(url) if direct else url, connect_timeout=15, prepare_threshold=None)


def migrate(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    conn.commit()


# ── 화면용 문서 ────────────────────────────────────────────────
def put_docs(conn, docs: Iterable[tuple[str, object]], prune: bool = True) -> int:
    """(경로, JSON)을 bundle_docs에 덮어쓴다. prune이면 이번에 안 나온 경로(사라진 지역 등)는 지운다.
    호출한 쪽에서 commit해야 반영된다(daily_sync는 전체를 한 트랜잭션으로)."""
    from psycopg.types.json import Jsonb
    paths = []
    with conn.cursor() as cur:
        for path, doc in docs:
            cur.execute("INSERT INTO bundle_docs (path, doc, updated_at) VALUES (%s, %s, now()) "
                        "ON CONFLICT (path) DO UPDATE SET doc = EXCLUDED.doc, updated_at = now()",
                        (path, Jsonb(doc)))
            paths.append(path)
        if prune:
            cur.execute("DELETE FROM bundle_docs WHERE NOT (path = ANY(%s))", (paths,))
    return len(paths)


def get_doc(conn, path: str):
    with conn.cursor() as cur:
        cur.execute("SELECT doc FROM bundle_docs WHERE path = %s", (path,))
        row = cur.fetchone()
    return row[0] if row else None


def doc_paths(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT path FROM bundle_docs ORDER BY path")
        return [r[0] for r in cur.fetchall()]


# ── 스냅샷·최신본·변경 이력 (pipeline 전용) ─────────────────────
def snapshot_dates(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT snapshot_date::text FROM snapshots ORDER BY snapshot_date")
        return [r[0] for r in cur.fetchall()]


def snapshot_by_sha(conn, sha: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT snapshot_date::text FROM snapshots WHERE sha256 = %s", (sha,))
        row = cur.fetchone()
    return row[0] if row else None


def record_snapshot(conn, date: str, sha: str, rows: int, source_url: str) -> None:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO snapshots (snapshot_date, sha256, rows, source_url) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (snapshot_date) DO UPDATE SET sha256 = EXCLUDED.sha256, rows = EXCLUDED.rows, "
                    "source_url = EXCLUDED.source_url, ingested_at = now()", (date, sha, rows, source_url))


def load_current(conn) -> "pd.DataFrame":
    import pandas as pd
    with conn.cursor() as cur:
        cur.execute("SELECT record FROM wifi_current")
        rows = [r[0] for r in cur.fetchall()]
    return pd.DataFrame(rows)


def replace_current(conn, clean: "pd.DataFrame") -> None:
    """wifi_current를 이번 정제 결과로 통째로 바꾼다(COPY)."""
    records = json.loads(clean.to_json(orient="records", force_ascii=False))
    with conn.cursor() as cur:
        cur.execute("TRUNCATE wifi_current")
        with cur.copy("COPY wifi_current (key, region_id, sido, sigungu, place_name, ssid, lat, lng, geom, record) "
                      "FROM STDIN") as cp:
            for rec in records:
                lat, lng = float(rec["lat"]), float(rec["lng"])
                cp.write_row((rec["key"], rec["region_id"], rec["sido"], rec["sigungu"], rec.get("place_name"),
                              rec.get("ssid"), lat, lng, f"SRID=4326;POINT({lng} {lat})",
                              json.dumps(rec, ensure_ascii=False)))


def add_changes(conn, changes: "pd.DataFrame") -> int:
    if changes.empty:
        return 0
    rows = [tuple(None if v != v else v for v in r)   # NaN → NULL
            for r in changes[["snapshot_from", "snapshot_to", "key", "change", "region_id", "sido", "sigungu",
                              "place_name", "ssid", "lat", "lng"]].itertuples(index=False)]
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO wifi_changes (snapshot_from, snapshot_to, key, change, region_id, sido, sigungu, "
                        "place_name, ssid, lat, lng) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT DO NOTHING", rows)
    return len(rows)


def load_changes(conn) -> "pd.DataFrame":
    import pandas as pd
    from wifisafe.changes import CHANGE_COLS
    with conn.cursor() as cur:
        cur.execute("SELECT snapshot_from::text, snapshot_to::text, key, change, region_id, sido, sigungu, "
                    "coalesce(place_name, ''), coalesce(ssid, ''), lat, lng FROM wifi_changes")
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=CHANGE_COLS)


# ── GPS 최근접 지역 (#18) ───────────────────────────────────────
def nearest_region(conn, lat: float, lng: float) -> dict | None:
    """좌표에서 가장 가까운 와이파이 지점의 region_id (PostGIS KNN)."""
    with conn.cursor() as cur:
        cur.execute("SELECT region_id, ST_Distance(geom, ST_MakePoint(%s, %s)::geography) "
                    "FROM wifi_current ORDER BY geom <-> ST_MakePoint(%s, %s)::geography LIMIT 1",
                    (lng, lat, lng, lat))
        row = cur.fetchone()
    return {"region_id": row[0], "distance_m": round(float(row[1]), 1)} if row else None


# ── 회원 (#19) ─────────────────────────────────────────────────
_USER_COLS = "id, provider, display_name, sido, sigungu, region_id"


def _user(row) -> dict | None:
    if not row:
        return None
    return dict(zip(["id", "provider", "display_name", "sido", "sigungu", "region_id"], row))


def upsert_user(conn, provider: str, provider_id: str, display_name: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO users (provider, provider_id, display_name) VALUES (%s, %s, %s) "
                    f"ON CONFLICT (provider, provider_id) DO UPDATE SET display_name = EXCLUDED.display_name, "
                    f"updated_at = now() RETURNING {_USER_COLS}", (provider, provider_id, display_name))
        row = cur.fetchone()
    conn.commit()
    return _user(row)


def get_user(conn, user_id: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_USER_COLS} FROM users WHERE id = %s", (user_id,))
        return _user(cur.fetchone())


def set_user_region(conn, user_id: int, sido: str, sigungu: str | None, region_id: str | None) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(f"UPDATE users SET sido = %s, sigungu = %s, region_id = %s, updated_at = now() WHERE id = %s "
                    f"RETURNING {_USER_COLS}", (sido, sigungu, region_id, user_id))
        row = cur.fetchone()
    conn.commit()
    return _user(row)


# ── 장소 검색 (장소명·주소·설치장소상세) ─────────────────────────
def _like_tokens(q: str) -> list[str]:
    esc = lambda t: t.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")   # noqa: E731
    return [f"%{esc(t)}%" for t in q.split() if t][:6]


def search_points(conn, q: str, region_id: str | None = None, limit: int = 20) -> list[dict]:
    """장소명·도로명주소·지번주소·설치장소상세에서 띄어쓰기로 나눈 단어를 모두 포함하는 지점.
    정렬: 지금 보는 지역 → 이름에 첫 단어가 든 것 → 이름순."""
    toks = _like_tokens(q)
    if not toks:
        return []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT key, region_id, sido, sigungu, place_name, record->>'address', record->>'place_detail', lat, lng "
            "FROM wifi_current "
            "WHERE concat_ws(' ', place_name, record->>'road_address', record->>'jibun_address', record->>'place_detail', "
            "                sido, sigungu) "
            "      ILIKE ALL (%s) "
            "ORDER BY (region_id = %s) DESC, (place_name ILIKE %s) DESC, place_name, key LIMIT %s",
            (toks, region_id or "", toks[0], limit))
        rows = cur.fetchall()
    cols = ["key", "region_id", "sido", "sigungu", "name", "address", "place_detail", "lat", "lng"]
    return [dict(zip(cols, r)) for r in rows]
