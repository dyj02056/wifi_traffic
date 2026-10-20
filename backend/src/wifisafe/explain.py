"""지점 위험요인 설명문 — AI(근거값만 인용) 또는 템플릿 (plan.md §8.4).

AI 출력은 guardrails.check_explanation()을 통과해야 쓰고, 하나라도 실패하면 템플릿으로 대체한다.
ANTHROPIC_API_KEY가 없으면 템플릿만 쓴다.
"""
from __future__ import annotations

import json
import os

from wifisafe import guardrails
from wifisafe.io import now_iso

DEFAULT_MODEL = "claude-haiku-5-5"

SYSTEM_PROMPT = """너는 공공와이파이 지점의 위험요인 점수를 시민에게 설명하는 안내문 작성자다.
규칙:
- 아래 JSON에 있는 값만 인용한다. 새로운 수치·사건·통계를 만들지 않는다.
- 2~3문장, 존댓말, 쉬운 단어.
- '해킹 확률', '해킹될 확률', '위험 지역' 같은 표현을 쓰지 않는다.
- 점수가 높은 항목 1~2개의 이유를 근거값과 함께 말하고, 마지막 문장은 행동 하나를 권한다.
- 설명문만 출력한다. 머리말·따옴표·목록 기호를 붙이지 않는다."""

TEMPLATE = "{place}의 위험요인 점수는 {score}점({grade})입니다. 가장 큰 요인은 {top1_name}({top1_evidence})입니다. {tip}."


def _fmt_score(score: float) -> str:
    return f"{score:.2f}".rstrip("0").rstrip(".")


def build_payload(detail: dict) -> dict:
    top = sorted(detail["breakdown"], key=lambda b: -b["points"])[:3]
    return {
        "place": detail["name"],
        "score": _fmt_score(detail["score"]),
        "grade": detail["grade"],
        "top_factors": [{"name": b["name"], "points": b["points"], "max_points": b["max_points"],
                         "evidence": b["reason"], "is_assumption": b["is_assumption"]} for b in top],
        "evidence": detail["evidence"],
        "recommended_action": detail["safety_tips"][0],
    }


def allowed_numbers_for(payload: dict) -> set[float]:
    vals = [payload["score"]]
    for f in payload["top_factors"]:
        vals += [f["name"], f["points"], f["max_points"], f["evidence"]]
    vals += list(payload["evidence"].values()) + [payload["place"], payload["recommended_action"]]
    return guardrails.allowed_numbers(vals)


def template_explanation(detail: dict) -> dict:
    top = max(detail["breakdown"], key=lambda b: b["points"])
    text = TEMPLATE.format(place=detail["name"], score=_fmt_score(detail["score"]), grade=detail["grade"],
                           top1_name=top["name"], top1_evidence=top["reason"],
                           tip=detail["safety_tips"][0].rstrip("."))
    return {"text": text, "source": "template", "model": None, "generated_at": now_iso()}


def ai_explanation(detail: dict, client=None, model: str | None = None) -> tuple[dict | None, list[str]]:
    """(설명 dict 또는 None, 실패 사유 목록)."""
    import anthropic
    model = model or os.environ.get("AI_MODEL", DEFAULT_MODEL)
    client = client or anthropic.Anthropic()
    payload = build_payload(detail)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=2048,
            output_config={"effort": "low"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
    except anthropic.RateLimitError as e:
        return None, [f"rate limit: {e.message}"]
    except anthropic.APIStatusError as e:
        return None, [f"API 오류 {e.status_code}: {e.message}"]
    except anthropic.APIConnectionError:
        return None, ["네트워크 오류"]
    if resp.stop_reason == "refusal":
        return None, ["refusal"]
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    problems = guardrails.check_explanation(text, allowed_numbers_for(payload))
    if problems:
        return None, problems
    return {"text": text, "source": "ai", "model": model, "generated_at": now_iso()}, []


def explain(detail: dict, use_ai: bool | None = None, client=None) -> tuple[dict, list[str]]:
    """AI 시도 후 실패하면 템플릿. 반환: (설명, AI 실패 사유)."""
    if use_ai is None:
        use_ai = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if use_ai:
        exp, problems = ai_explanation(detail, client=client)
        if exp:
            return exp, []
        return template_explanation(detail), problems
    return template_explanation(detail), []
