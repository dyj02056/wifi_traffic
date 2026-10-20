"""번들 JSON 읽기(로직 중복 없이 export_bundle 결과를 그대로 서빙)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_REGION_RE = re.compile(r"^[0-9]{2}-[a-z0-9-]+$")


class BundleStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        if not (self.root / "meta.json").exists():
            raise RuntimeError(f"번들이 없습니다: {self.root} (python pipeline/export_bundle.py 또는 BUNDLE_DIR 지정)")
        self.key_index: dict[str, str] = self._read("key_index.json")
        self._cache = lru_cache(maxsize=64)(self._read)

    def _read(self, rel: str):
        with open(self.root / rel, encoding="utf-8") as f:
            return json.load(f)

    def get(self, rel: str):
        return self._cache(rel)

    def region_file(self, folder: str, region_id: str):
        """없는 지역이면 None. region_id 형식을 검사해 경로 이탈을 막는다."""
        if not _REGION_RE.match(region_id) or not (self.root / folder / f"{region_id}.json").exists():
            return None
        return self.get(f"{folder}/{region_id}.json")

    def detail(self, key: str):
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
        try:
            return fn(self.conn(), *args)
        except Exception:
            self._conn = None
            return fn(self.conn(), *args)

    CACHE_TTL = 600   # 초. daily_sync가 DB를 바꾼 뒤 최대 10분 안에 새 문서를 내준다

    def get(self, rel: str):
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
        if not _REGION_RE.match(region_id):
            return None
        return self.get(f"{folder}/{region_id}.json")

    def detail(self, key: str):
        """지역 상세 문서(수 MB) 전체 대신 그 지점만 jsonb에서 꺼낸다."""
        rid = (self.get("key_index.json") or {}).get(key)
        if rid is None:
            return None

        def one(conn, path, k):
            with conn.cursor() as cur:
                cur.execute("SELECT doc -> %s FROM bundle_docs WHERE path = %s", (k, path))
                row = cur.fetchone()
            return row[0] if row else None
        return self._query(one, f"detail/{rid}.json", key)
