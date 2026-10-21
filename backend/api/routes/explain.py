"""POST /api/points/{key}/explain — 실시간 AI 설명(선택). 키가 없거나 가드레일 실패 시 템플릿. 결과는 메모리 캐시.

[이 파일이 하는 일]
  화면에서 지점 설명을 새로 만들어 달라고 요청하면(POST), AI 또는 템플릿으로 설명문을 만들어 돌려줍니다.
  한 번 만든 설명은 서버 메모리에 기억해 두었다가(캐시) 같은 지점을 다시 물으면 바로 돌려줍니다.
  (서버가 다시 시작되면 기억은 사라집니다.)
"""
import os

from fastapi import APIRouter, HTTPException, Request

from api import models as M
from wifisafe.explain import explain

router = APIRouter(prefix="/api")
# 지점키 → 만들어 둔 응답
_cache: dict[str, dict] = {}


# POST /api/points/{key}/explain
@router.post("/points/{key}/explain", response_model=M.ExplainResponse)
def explain_point(key: str, request: Request):
    d = request.app.state.store.detail(key)
    if d is None:
        raise HTTPException(404, f"없는 지점 key: {key}")
    ai = bool(os.environ.get("ANTHROPIC_API_KEY"))   # AI 키가 설정돼 있으면 AI 사용 가능
    if key in _cache:
        return {**_cache[key], "cached": True}
    exp, problems = explain(d, use_ai=ai)
    res = {"key": key, "ai_available": ai, "cached": False, "explanation": exp, "ai_rejected_reasons": problems}
    # AI 설명에 성공했거나 AI를 아예 안 쓰는 경우만 기억한다.
    # (AI가 실패해 템플릿을 쓴 경우는 다음 요청 때 AI를 다시 시도할 수 있게 기억하지 않는다.)
    if exp["source"] == "ai" or not ai:
        _cache[key] = res
    return res
