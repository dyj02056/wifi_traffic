"""Neon 스키마 적용 (db/schema.sql, 여러 번 실행해도 안전).

[이 파일이 하는 일]
  데이터베이스에 필요한 표(테이블)들을 만듭니다. 이미 있으면 그대로 둡니다.
  끝나면 PostGIS(지도 계산 기능) 버전과 만들어진 테이블 목록을 출력해 제대로 준비됐는지 보여 줍니다.
  처음 DB를 만들었을 때 한 번 실행하면 됩니다(daily_sync.py도 시작할 때 같은 일을 함).

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
