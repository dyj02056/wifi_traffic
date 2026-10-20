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
