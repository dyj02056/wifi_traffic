"""POST /api/points/{key}/explain — 실시간 AI 설명(선택). 키가 없거나 가드레일 실패 시 템플릿. 결과는 메모리 캐시."""
import os

from fastapi import APIRouter, HTTPException, Request

from api import models as M
from wifisafe.explain import explain

router = APIRouter(prefix="/api")
_cache: dict[str, dict] = {}


@router.post("/points/{key}/explain", response_model=M.ExplainResponse)
def explain_point(key: str, request: Request):
    d = request.app.state.store.detail(key)
    if d is None:
        raise HTTPException(404, f"없는 지점 key: {key}")
    ai = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if key in _cache:
        return {**_cache[key], "cached": True}
    exp, problems = explain(d, use_ai=ai)
    res = {"key": key, "ai_available": ai, "cached": False, "explanation": exp, "ai_rejected_reasons": problems}
    if exp["source"] == "ai" or not ai:
        _cache[key] = res
    return res
