"""사례 카드 로드. 출처(name·url)와 날짜(published_at·retrieved_at)가 없으면 에러 (plan.md §0-6).

[이 파일이 하는 일]
  /context 화면의 '같은 원리 사례' 카드(예: 해외의 가짜 와이파이 사건 기사)를 data/cases.yaml에서 읽어 옵니다.
  근거 없는 이야기가 화면에 나가지 않도록, 출처 이름·주소·발행일·확인일이 하나라도 빠지면 작업을 멈춥니다.
  사례는 점수에 반영하지 않습니다.
"""
from __future__ import annotations

import re
from pathlib import Path

from wifisafe.io import DATA_DIR, read_yaml

# 사례 카드 묶음에 붙는 안내 문구 (국내 공공와이파이에서 실제로 일어난 사건으로 오해하지 않도록)
LABEL = "같은 원리 사례 — 국내 공공와이파이 사건 아님"
# 날짜 모양 검사: 2026-10-21 처럼 '네 자리-두 자리-두 자리'
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CaseSourceError(SystemExit):
    """사례 카드에 출처·날짜·필수 내용이 빠졌을 때 내는 오류."""
    pass


def load_cases(path: Path | None = None) -> dict:
    """cases.yaml을 읽어 cases.json 모양으로 돌려준다. 파일이 없으면 빈 목록."""
    path = path or DATA_DIR / "cases.yaml"
    doc = read_yaml(path) if path.exists() else {}
    out = []
    for i, c in enumerate(doc.get("cases") or []):
        cid = c.get("id") or f"#{i}"
        src = c.get("source") or {}
        # 빠진 출처 항목 모으기: 이름·주소가 비었거나, 날짜가 YYYY-MM-DD 모양이 아니면 '누락'
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
