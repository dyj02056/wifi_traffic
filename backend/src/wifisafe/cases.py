"""사례 카드 로드. 출처(name·url)와 날짜(published_at·retrieved_at)가 없으면 에러 (plan.md §0-6)."""
from __future__ import annotations

import re
from pathlib import Path

from wifisafe.io import DATA_DIR, read_yaml

LABEL = "같은 원리 사례 — 국내 공공와이파이 사건 아님"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CaseSourceError(SystemExit):
    pass


def load_cases(path: Path | None = None) -> dict:
    path = path or DATA_DIR / "cases.yaml"
    doc = read_yaml(path) if path.exists() else {}
    out = []
    for i, c in enumerate(doc.get("cases") or []):
        cid = c.get("id") or f"#{i}"
        src = c.get("source") or {}
        missing = [k for k in ("name", "url") if not src.get(k)]
        missing += [k for k in ("published_at", "retrieved_at") if not _DATE.match(str(src.get(k) or ""))]
        if missing:
            raise CaseSourceError(f"cases.yaml 사례 {cid}: 출처·날짜 누락 {missing} — 출처 없는 사례는 렌더링 금지")
        for k in ("title", "summary", "principle"):
            if not c.get(k):
                raise CaseSourceError(f"cases.yaml 사례 {cid}: '{k}' 누락")
        out.append({
            "id": c["id"], "title": c["title"], "summary": c["summary"], "principle": c["principle"],
            "related_rules": list(c.get("related_rules") or []),
            "source": {"name": src["name"], "dataset_id": None, "url": src["url"],
                       "published_at": str(src["published_at"]), "retrieved_at": str(src["retrieved_at"])},
        })
    return {"label": LABEL, "cases": out}
