"""Neon 스키마 적용 (db/schema.sql, 여러 번 실행해도 안전).

실행: python pipeline/db_migrate.py      (backend/.env의 DATABASE_URL 사용)
"""
import _bootstrap  # noqa: F401

from wifisafe.db import connect, migrate


def main():
    with connect(direct=True) as conn:
        migrate(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT postgis_version()")
            pg = cur.fetchone()[0]
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' "
                        "AND table_name IN ('snapshots','wifi_current','wifi_changes','bundle_docs','users') "
                        "ORDER BY table_name")
            tables = [r[0] for r in cur.fetchall()]
    print(f"[db_migrate] PostGIS {pg}, 테이블 {tables}")


if __name__ == "__main__":
    main()
