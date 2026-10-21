"""지점 위험요인 설명문 — AI(근거값만 인용) 또는 템플릿 (plan.md §8.4).

[이 파일이 하는 일]
  지점 상세 화면에 나오는 2~3문장짜리 쉬운 설명을 만듭니다.
  예) "○○역 와이파이의 위험요인 점수는 72점으로 '높음' 단계입니다. 이곳은 비밀번호 없이 연결되는 개방형 와이파이이고, …"
  두 가지 방법이 있습니다.
    1) 템플릿: 정해진 문장 틀에 값만 끼워 넣는다. 언제나 쓸 수 있고 결과가 예측 가능하다.
    2) AI: Claude(Anthropic의 AI 모델)에게 근거값을 주고 문장을 쓰게 한다. 더 자연스럽지만 틀린 말을 할 위험이 있다.

AI 출력은 guardrails.check_explanation()을 통과해야 쓰고, 하나라도 실패하면 템플릿으로 대체한다.
(guardrails: AI가 근거에 없는 숫자를 지어내거나 '해킹 확률' 같은 금지 표현을 쓰지 않았는지 검사)
ANTHROPIC_API_KEY가 없으면 템플릿만 쓴다.
"""
from __future__ import annotations

import json
import os
import re

from wifisafe import guardrails
from wifisafe.io import now_iso

# 기본으로 쓸 AI 모델 이름 (환경변수 AI_MODEL로 바꿀 수 있음)
DEFAULT_MODEL = "claude-haiku-5-5"

# AI에게 주는 '작성 규칙'. AI는 이 규칙을 따르며 설명문을 쓴다.
SYSTEM_PROMPT = """너는 공공와이파이 지점의 위험요인 점수를 시민에게 설명하는 안내문 작성자다.
규칙:
- 아래 JSON에 있는 값만 인용한다. 새로운 수치·사건·통계를 만들지 않는다.
- 2~3문장, 존댓말, 쉬운 단어.
- '해킹 확률', '해킹될 확률', '위험 지역' 같은 표현을 쓰지 않는다.
- 점수가 높은 항목 1~2개의 이유를 근거값과 함께 말하고, 마지막 문장은 행동 하나를 권한다.
- 설명문만 출력한다. 머리말·따옴표·목록 기호를 붙이지 않는다."""

# 템플릿 문장 틀. {중괄호} 자리에 실제 값이 들어간다.
TEMPLATE = "{place} 와이파이의 위험요인 점수는 {score}점으로 '{grade}' 단계입니다. {factors} {tip}."
# 데이터가 없어 가정값을 쓴 요인 뒤에 붙이는 말
ASSUMED = "(정보가 없어 추정)"

# 시설구분 → 쉬운 말 (config/facility_map.csv와 같은 분류)
FACILITY_PLAIN = {
    "교통시설": "정류장·역사처럼 많은 사람이 짧게 머물며 오가는 곳",
    "관광": "관광지·공원처럼 외지인이 잠깐 접속하는 곳",
    "편의시설": "여러 사람이 잠깐씩 오가는 편의시설",
    "기타": "여러 유형이 섞인 생활 공간",
    "지역문화시설": "도서관·마을회관처럼 주민이 주로 쓰는 시설",
    "관공서": "민원실·보건소처럼 정해진 용무로 찾는 곳",
    "서민·복지시설": "경로당처럼 정해진 이용자가 머무는 시설",
    "교육시설": "등록된 이용자가 주로 쓰는 교육시설",
}
# 숫자(정수 또는 소수)를 찾는 패턴. 예) "8", "3.5"
_NUM = r"(\d+(?:\.\d+)?)"


def _plain(b: dict) -> str:
    """규칙 하나의 근거(reason)를 쉬운 명사구로. 숫자는 reason에 있는 것만 그대로 옮긴다.

    b는 breakdown(요인별 점수 내역)의 한 항목. 예) R4 reason "설치 후 약 6.2년 경과" → "설치한 지 약 6.2년 된 장비"
    """
    rid, reason = b["id"], b["reason"]
    assumed = "가정 비율 적용" in reason or ("없음" in reason and rid in ("R4", "R8"))
    if rid == "R1":
        text = ("비밀번호 없이 연결되는 개방형 와이파이" if "개방형" in reason
                else "보안접속을 함께 제공하는지 확인되지 않은 정부 공공와이파이" if "Free" in reason
                else "보안 방식을 확인할 수 없는 와이파이")
    elif rid == "R2":
        m = re.search(r"시설구분 '([^']+)'", reason)
        ft = m.group(1) if m else ""
        text = FACILITY_PLAIN.get(ft, f"'{ft}'(으)로 분류된 시설" if ft else "시설 유형을 알 수 없는 곳")
    elif rid == "R3":
        m = re.search(r"실외 키워드 '([^']+)'", reason)
        text = f"실외('{m.group(1)}')에 설치된 장비" if m else "실외에 설치된 장비"
    elif rid == "R4":
        m = re.search(r"약 " + _NUM + "년", reason)
        text = f"설치한 지 약 {m.group(1)}년 된 장비" if m else "설치 시기를 알 수 없는 장비"
    elif rid == "R5":
        m = re.search(r"반경 " + _NUM + r"m 안 개방형 AP " + _NUM + "개", reason)
        text = (f"반경 {m.group(1)}m 안에 개방형 와이파이가 {m.group(2)}개 있는 곳" if m
                else "주변에 개방형 와이파이가 많은 곳")
    elif rid == "R6":
        text = "제공사·관리기관 정보가 비어 있는 와이파이"
    elif rid == "R7":
        text = "관리기관 전화번호가 올바르지 않은 와이파이" if "형식" in reason else "관리기관 전화번호가 없는 와이파이"
    elif rid == "R8":
        m = re.search(r"기준일자 후 " + _NUM + "일", reason)
        text = f"공개 데이터 기준일에서 {m.group(1)}일이 지난 정보" if m else "데이터 기준일자가 없는 정보"
    else:
        text = b["name"]
    return text + (ASSUMED if assumed else "")


def _factors_sentence(breakdown: list[dict], max_items: int = 2) -> str:
    """점수가 가장 큰 요인 1~2개로 "이곳은 ~이고, ~입니다." 문장을 만든다."""
    top = [b for b in sorted(breakdown, key=lambda b: -b["points"]) if b["points"] > 0][:max_items]
    if not top:
        return "눈에 띄는 위험요인은 없습니다."
    parts = [_plain(b) for b in top]
    return "이곳은 " + "이고, ".join(parts) + "입니다."


def _fmt_score(score: float) -> str:
    """점수를 보기 좋게: 72.50 → "72.5", 60.00 → "60" (끝의 0과 소수점을 지움)"""
    return f"{score:.2f}".rstrip("0").rstrip(".")


def build_payload(detail: dict) -> dict:
    """AI에게 보낼 자료: 장소명·점수·등급·상위 3개 요인과 근거·원본 값·권장 행동. AI는 이 안의 값만 인용할 수 있다."""
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
    """AI 설명문에 나와도 되는 숫자 목록: 보낸 자료 안에 들어 있는 숫자만 허용한다."""
    vals = [payload["score"]]
    for f in payload["top_factors"]:
        vals += [f["name"], f["points"], f["max_points"], f["evidence"]]
    vals += list(payload["evidence"].values()) + [payload["place"], payload["recommended_action"]]
    return guardrails.allowed_numbers(vals)


def template_explanation(detail: dict) -> dict:
    """템플릿으로 설명문을 만든다. source="template"로 표시해서 AI 설명과 구별한다."""
    text = TEMPLATE.format(place=detail["name"], score=_fmt_score(detail["score"]), grade=detail["grade"],
                           factors=_factors_sentence(detail["breakdown"]),
                           tip=detail["safety_tips"][0].rstrip("."))
    return {"text": text, "source": "template", "model": None, "generated_at": now_iso()}


def ai_explanation(detail: dict, client=None, model: str | None = None) -> tuple[dict | None, list[str]]:
    """(설명 dict 또는 None, 실패 사유 목록).

    AI에게 설명문을 요청하고, 검사(guardrails)를 통과하면 그 설명을 돌려준다.
    요청 한도 초과·서버 오류·네트워크 오류·AI의 답변 거절·검사 탈락이면 None과 사유를 돌려준다.
    """
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
    # AI 응답은 여러 조각으로 올 수 있어서 글자 조각만 이어 붙인다.
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    problems = guardrails.check_explanation(text, allowed_numbers_for(payload))
    if problems:
        return None, problems
    return {"text": text, "source": "ai", "model": model, "generated_at": now_iso()}, []


def explain(detail: dict, use_ai: bool | None = None, client=None) -> tuple[dict, list[str]]:
    """AI 시도 후 실패하면 템플릿. 반환: (설명, AI 실패 사유).

    use_ai를 따로 정하지 않으면, AI 키(ANTHROPIC_API_KEY)가 설정돼 있을 때만 AI를 쓴다.
    """
    if use_ai is None:
        use_ai = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if use_ai:
        exp, problems = ai_explanation(detail, client=client)
        if exp:
            return exp, []
        return template_explanation(detail), problems
    return template_explanation(detail), []
