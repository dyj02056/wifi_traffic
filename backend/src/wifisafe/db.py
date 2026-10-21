"""Neon(Postgres + PostGIS) 접근 (docs/requests.md #15·#18·#19).

[이 파일이 하는 일]
  인터넷에 있는 데이터베이스(Neon이라는 서비스의 PostgreSQL)에 접속해서 데이터를 넣고 꺼내는 함수 모음입니다.
  - 화면용 문서(번들 JSON) 저장·조회
  - 날짜별 스냅샷 기록, 최신 와이파이 목록, 추가·삭제 이력
  - 좌표로 가장 가까운 지역 찾기(PostGIS: 지도·거리 계산 기능을 더한 데이터베이스 확장)
  - 회원 정보 저장, 장소 검색
  테이블 구조는 backend/db/schema.sql에 있습니다.

[SQL 읽는 법 (간단히)]
  - SELECT … FROM 표 WHERE 조건 : 표에서 조건에 맞는 줄을 꺼낸다
  - INSERT … ON CONFLICT DO UPDATE : 새로 넣되, 이미 있으면 덮어쓴다 ('upsert')
  - %s 자리에는 뒤에 넘긴 값이 안전하게 채워진다(사용자 입력이 SQL 명령으로 해석되는 공격을 막음)
  - 함수 안에서 commit()을 해야 변경이 실제로 저장된다

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

# 테이블을 만드는 SQL 파일 위치
SCHEMA_SQL = BACKEND_DIR / "db" / "schema.sql"
# wifi_current 테이블에 따로 칸으로 두는 항목(나머지는 record 칸에 JSON으로 통째로 저장)
CURRENT_COLS = ["key", "region_id", "sido", "sigungu", "place_name", "ssid", "lat", "lng"]


def database_url(required: bool = True) -> str | None:
    """환경변수에서 DB 접속 주소를 읽는다. 없는데 required=True면 안내 문구와 함께 멈춘다."""
    load_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url and required:
        raise SystemExit("DATABASE_URL이 없습니다. backend/.env에 Neon 연결 문자열을 넣으세요(채팅·코드에 쓰지 말 것).")
    return url or None


def direct_url(url: str) -> str:
    """Neon 풀러 주소(ep-xxx-pooler.…)를 직접 연결 주소(ep-xxx.…)로. 긴 트랜잭션·대량 저장(daily_sync)은 직접 연결이 안전하다.

    (풀러: 여러 접속을 나눠 쓰게 해 주는 중간 관리자. 짧은 요청이 많은 API에 유리하다.)
    """
    return url.replace("-pooler.", ".", 1)


def connect(url: str | None = None, direct: bool = False) -> "psycopg.Connection":
    """API는 풀러 주소 그대로, pipeline(direct=True)은 직접 연결. 풀러에서도 동작하도록 서버측 prepared statement는 끈다."""
    import psycopg
    url = url or database_url()
    return psycopg.connect(direct_url(url) if direct else url, connect_timeout=15, prepare_threshold=None)


def migrate(conn) -> None:
    """schema.sql을 실행해 테이블을 만든다(이미 있으면 그대로 둠)."""
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    conn.commit()


# ── 화면용 문서 ────────────────────────────────────────────────
def put_docs(conn, docs: Iterable[tuple[str, object]], prune: bool = True) -> int:
    """(경로, JSON)을 bundle_docs에 덮어쓴다. prune이면 이번에 안 나온 경로(사라진 지역 등)는 지운다.
    호출한 쪽에서 commit해야 반영된다(daily_sync는 전체를 한 트랜잭션으로).

    (트랜잭션: 여러 작업을 '전부 성공 아니면 전부 취소'로 묶는 단위. 중간에 실패해도 반쯤 바뀐 상태가 남지 않는다.)
    돌려주는 값: 저장한 문서 수
    """
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
    """경로(예: "points/41-goyang.json")로 문서 하나를 꺼낸다. 없으면 None."""
    with conn.cursor() as cur:
        cur.execute("SELECT doc FROM bundle_docs WHERE path = %s", (path,))
        row = cur.fetchone()
    return row[0] if row else None


def doc_paths(conn) -> list[str]:
    """저장된 모든 문서 경로 목록."""
    with conn.cursor() as cur:
        cur.execute("SELECT path FROM bundle_docs ORDER BY path")
        return [r[0] for r in cur.fetchall()]


# ── 스냅샷·최신본·변경 이력 (pipeline 전용) ─────────────────────
def snapshot_dates(conn) -> list[str]:
    """지금까지 저장한 스냅샷 날짜 목록(오래된 순)."""
    with conn.cursor() as cur:
        cur.execute("SELECT snapshot_date::text FROM snapshots ORDER BY snapshot_date")
        return [r[0] for r in cur.fetchall()]


def snapshot_by_sha(conn, sha: str) -> str | None:
    """파일 지문(sha256)이 같은 스냅샷이 이미 있으면 그 날짜를 돌려준다(같은 파일을 두 번 넣지 않기 위함).

    (sha256: 파일 내용으로 계산한 고유 지문. 내용이 한 글자라도 다르면 지문이 완전히 달라진다.)
    """
    with conn.cursor() as cur:
        cur.execute("SELECT snapshot_date::text FROM snapshots WHERE sha256 = %s", (sha,))
        row = cur.fetchone()
    return row[0] if row else None


def record_snapshot(conn, date: str, sha: str, rows: int, source_url: str) -> None:
    """스냅샷 한 건(날짜·지문·행 수·받은 주소)을 기록한다. 같은 날짜가 있으면 덮어쓴다."""
    with conn.cursor() as cur:
        cur.execute("INSERT INTO snapshots (snapshot_date, sha256, rows, source_url) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (snapshot_date) DO UPDATE SET sha256 = EXCLUDED.sha256, rows = EXCLUDED.rows, "
                    "source_url = EXCLUDED.source_url, ingested_at = now()", (date, sha, rows, source_url))


def load_current(conn) -> "pd.DataFrame":
    """DB에 저장된 최신 와이파이 목록(지난번 정제 결과)을 표로 꺼낸다."""
    import pandas as pd
    with conn.cursor() as cur:
        cur.execute("SELECT record FROM wifi_current")
        rows = [r[0] for r in cur.fetchall()]
    return pd.DataFrame(rows)


def replace_current(conn, clean: "pd.DataFrame") -> None:
    """wifi_current를 이번 정제 결과로 통째로 바꾼다(COPY).

    TRUNCATE로 표를 비운 뒤 COPY(대량으로 빠르게 넣는 명령)로 전부 다시 넣는다.
    geom 칸에는 'SRID=4326;POINT(경도 위도)' 모양의 지도 좌표를 넣는다(4326 = GPS가 쓰는 세계 좌표계 번호).
    """
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
    """추가·삭제 기록을 wifi_changes에 쌓는다. 이미 있는 기록은 건너뛴다. 돌려주는 값: 넣으려 한 줄 수."""
    if changes.empty:
        return 0
    rows = [tuple(None if v != v else v for v in r)   # NaN → NULL  (NaN은 자기 자신과 같지 않다는 성질을 이용)
            for r in changes[["snapshot_from", "snapshot_to", "key", "change", "region_id", "sido", "sigungu",
                              "place_name", "ssid", "lat", "lng"]].itertuples(index=False)]
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO wifi_changes (snapshot_from, snapshot_to, key, change, region_id, sido, sigungu, "
                        "place_name, ssid, lat, lng) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT DO NOTHING", rows)
    return len(rows)


def load_changes(conn) -> "pd.DataFrame":
    """지금까지 쌓인 추가·삭제 기록 전체를 표로 꺼낸다."""
    import pandas as pd
    from wifisafe.changes import CHANGE_COLS
    with conn.cursor() as cur:
        cur.execute("SELECT snapshot_from::text, snapshot_to::text, key, change, region_id, sido, sigungu, "
                    "coalesce(place_name, ''), coalesce(ssid, ''), lat, lng FROM wifi_changes")
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=CHANGE_COLS)


# ── GPS 최근접 지역 (#18) ───────────────────────────────────────
def nearest_region(conn, lat: float, lng: float) -> dict | None:
    """좌표에서 가장 가까운 와이파이 지점의 region_id (PostGIS KNN).

    (KNN: '가장 가까운 이웃 찾기'. `<->` 연산자가 거리 순 정렬을 빠르게 해 준다.)
    돌려주는 값 예) {"region_id": "41-goyang", "distance_m": 120.5}
    """
    with conn.cursor() as cur:
        cur.execute("SELECT region_id, ST_Distance(geom, ST_MakePoint(%s, %s)::geography) "
                    "FROM wifi_current ORDER BY geom <-> ST_MakePoint(%s, %s)::geography LIMIT 1",
                    (lng, lat, lng, lat))
        row = cur.fetchone()
    return {"region_id": row[0], "distance_m": round(float(row[1]), 1)} if row else None


# ── 회원 (#19) ─────────────────────────────────────────────────
_USER_COLS = "id, provider, display_name, sido, sigungu, region_id"


def _user(row) -> dict | None:
    """DB에서 꺼낸 한 줄(튜플)을 {"id": …, "provider": …} 모양으로 바꾼다."""
    if not row:
        return None
    return dict(zip(["id", "provider", "display_name", "sido", "sigungu", "region_id"], row))


def upsert_user(conn, provider: str, provider_id: str, display_name: str) -> dict:
    """소셜 로그인한 사용자를 저장한다. 처음이면 새로 만들고, 이미 있으면 표시 이름만 갱신한다.

    - provider: "google" 또는 "naver", provider_id: 그 서비스가 알려 준 사용자 고유번호
    """
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO users (provider, provider_id, display_name) VALUES (%s, %s, %s) "
                    f"ON CONFLICT (provider, provider_id) DO UPDATE SET display_name = EXCLUDED.display_name, "
                    f"updated_at = now() RETURNING {_USER_COLS}", (provider, provider_id, display_name))
        row = cur.fetchone()
    conn.commit()
    return _user(row)


def get_user(conn, user_id: int) -> dict | None:
    """회원 번호로 회원 정보를 꺼낸다."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_USER_COLS} FROM users WHERE id = %s", (user_id,))
        return _user(cur.fetchone())


def set_user_region(conn, user_id: int, sido: str, sigungu: str | None, region_id: str | None) -> dict | None:
    """회원이 고른 '사는 지역'을 저장한다."""
    with conn.cursor() as cur:
        cur.execute(f"UPDATE users SET sido = %s, sigungu = %s, region_id = %s, updated_at = now() WHERE id = %s "
                    f"RETURNING {_USER_COLS}", (sido, sigungu, region_id, user_id))
        row = cur.fetchone()
    conn.commit()
    return _user(row)


# ── 장소 검색 (장소명·주소·설치장소상세) ─────────────────────────
def _like_tokens(q: str) -> list[str]:
    """검색어를 띄어쓰기로 나눠 SQL LIKE 패턴('%단어%')으로 만든다. 최대 6단어.

    %와 _는 LIKE에서 특수 문자라서, 사용자가 입력한 %·_는 앞에 \\를 붙여 글자 그대로 찾게 한다.
    """
    esc = lambda t: t.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")   # noqa: E731
    return [f"%{esc(t)}%" for t in q.split() if t][:6]


def search_points(conn, q: str, region_id: str | None = None, limit: int = 20) -> list[dict]:
    """장소명·도로명주소·지번주소·설치장소상세에서 띄어쓰기로 나눈 단어를 모두 포함하는 지점.
    정렬: 지금 보는 지역 → 이름에 첫 단어가 든 것 → 이름순.

    (ILIKE ALL: 대소문자 구분 없이, 모든 패턴을 다 포함하는 줄만)
    """
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
