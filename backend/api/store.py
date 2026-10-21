"""번들 JSON 읽기(로직 중복 없이 export_bundle 결과를 그대로 서빙).

[이 파일이 하는 일]
  API가 화면에 내줄 번들 문서를 꺼내 오는 '창고' 두 종류를 정의합니다. 둘 다 같은 사용법(get, region_file, detail)을 가집니다.
    - BundleStore: 컴퓨터 폴더에 저장된 JSON 파일에서 읽는다 (개발·테스트용, 백업)
    - DbStore: Neon 데이터베이스의 bundle_docs 테이블에서 읽는다 (실제 배포용)
  자주 쓰는 문서는 잠시 기억해 두어(캐시) 매번 다시 읽지 않습니다.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

# 올바른 region_id 모양: 숫자 두 자리 + 하이픈 + 영문 소문자·숫자·하이픈. 예) "41-goyang"
# 이 검사로 "../../비밀파일" 같은 주소로 다른 폴더 파일을 몰래 읽으려는 시도를 막는다.
_REGION_RE = re.compile(r"^[0-9]{2}-[a-z0-9-]+$")


class BundleStore:
    # 폴더에 저장된 번들 파일을 읽는 창고
    def __init__(self, root: Path):
        self.root = Path(root)
        if not (self.root / "meta.json").exists():
            raise RuntimeError(f"번들이 없습니다: {self.root} (python pipeline/export_bundle.py 또는 BUNDLE_DIR 지정)")
        self.key_index: dict[str, str] = self._read("key_index.json")   # 지점키 → 지역 (상세 찾기용)
        self._cache = lru_cache(maxsize=64)(self._read)                  # 최근 읽은 파일 64개를 기억

    def _read(self, rel: str):
        # 번들 폴더 안의 상대 경로 파일을 JSON으로 읽는다
        with open(self.root / rel, encoding="utf-8") as f:
            return json.load(f)

    def get(self, rel: str):
        # 문서 하나 꺼내기(캐시 사용). 예) get("rules.json")
        return self._cache(rel)

    def region_file(self, folder: str, region_id: str):
        """없는 지역이면 None. region_id 형식을 검사해 경로 이탈을 막는다."""
        if not _REGION_RE.match(region_id) or not (self.root / folder / f"{region_id}.json").exists():
            return None
        return self.get(f"{folder}/{region_id}.json")

    def detail(self, key: str):
        # 지점 하나의 상세 정보: key_index로 지역을 찾고 → 그 지역 상세 파일에서 지점을 꺼낸다
        rid = self.key_index.get(key)
        if rid is None:
            return None
        return (self.region_file("detail", rid) or {}).get(key)


class DbStore:
    """Neon(bundle_docs)에서 같은 문서를 읽는다(docs/requests.md #15). BundleStore와 같은 메서드."""

    def __init__(self, url: str):
        from wifisafe import db
        self._db = db
        self._url = url
        self._conn = None
        self._cache: dict[str, tuple[float, object]] = {}   # 경로 → (읽은 시각, 문서). 매일 갱신을 반영하도록 CACHE_TTL만 보관

    def conn(self):
        """연결을 재사용하고, 끊겼으면(Neon 유휴 정지 등) 다시 연결한다."""
        if self._conn is None or self._conn.closed or self._conn.broken:
            self._conn = self._db.connect(self._url)
            self._conn.autocommit = True
        return self._conn

    def _query(self, fn, *args):
        # DB 작업을 실행한다. 실패하면(연결이 끊겼을 수 있음) 연결을 새로 만들어 한 번 더 시도한다.
        try:
            return fn(self.conn(), *args)
        except Exception:
            self._conn = None
            return fn(self.conn(), *args)

    CACHE_TTL = 600   # 초. daily_sync가 DB를 바꾼 뒤 최대 10분 안에 새 문서를 내준다

    def get(self, rel: str):
        # 문서 하나 꺼내기. 10분 안에 읽은 적이 있으면 기억해 둔 것을 돌려준다.
        import time
        hit = self._cache.get(rel)
        if hit and time.monotonic() - hit[0] < self.CACHE_TTL:
            return hit[1]
        doc = self._query(self._db.get_doc, rel)
        if doc is None:
            return None
        self._cache[rel] = (time.monotonic(), doc)
        return doc

    def region_file(self, folder: str, region_id: str):
        # 지역 파일 꺼내기. region_id 모양이 이상하면 None
        if not _REGION_RE.match(region_id):
            return None
        return self.get(f"{folder}/{region_id}.json")

    def detail(self, key: str):
        """지역 상세 문서(수 MB) 전체 대신 그 지점만 jsonb에서 꺼낸다."""
        rid = (self.get("key_index.json") or {}).get(key)
        if rid is None:
            return None

        def one(conn, path, k):
            # SQL의 `doc -> 키`: JSON 문서에서 그 키의 값만 꺼낸다
            with conn.cursor() as cur:
                cur.execute("SELECT doc -> %s FROM bundle_docs WHERE path = %s", (k, path))
                row = cur.fetchone()
            return row[0] if row else None
        return self._query(one, f"detail/{rid}.json", key)
