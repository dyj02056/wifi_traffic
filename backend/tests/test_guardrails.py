from wifisafe import guardrails as G
from wifisafe.explain import allowed_numbers_for, build_payload, explain, template_explanation


def test_forbidden_detected():
    assert "해킹 확률" in G.find_forbidden("이곳의 해킹 확률은 높습니다.")
    assert G.find_forbidden("범죄 다발 지역입니다.")


def test_disclaimer_negation_allowed():
    assert G.find_forbidden("이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.") == []


def test_unknown_numbers():
    allowed = G.allowed_numbers(["75.25", 30, "설치 후 약 9.6년 경과"])
    assert G.unknown_numbers("점수는 75.25점이고 9.6년 지났습니다.", allowed) == []
    assert G.unknown_numbers("점수는 75.25점, 사고 120건.", allowed) == ["120"]


def test_sentence_count():
    assert G.sentence_count("첫 문장입니다. 점수는 75.25점입니다. 조심하세요.") == 3


def _detail():
    bd = [{"id": f"R{i}", "name": f"규칙{i}", "ratio": 1.0 if i == 1 else 0.0, "points": 30.0 if i == 1 else 0.0,
           "max_points": 30 if i == 1 else 5, "is_assumption": False,
           "reason": "SSID가 개방형 목록에 있음" if i == 1 else "해당 없음"} for i in range(1, 9)]
    return {"key": "0123456789", "region_id": "11-guro", "name": "샘플 정류장", "score": 30.0, "grade": "주의",
            "evidence": {"ssid": "X", "facility_type": None, "place_detail": None, "install_ym": "2017-03",
                         "provider": None, "manager": None, "manager_tel": "02-000-0000", "data_date": "2026-10-18",
                         "address": None, "open_ap_within_radius": 2},
            "breakdown": bd, "safety_tips": ["같은 장소에 보안접속 SSID가 보이면 그쪽으로 연결하세요"]}


def test_template_passes_guardrails():
    d = _detail()
    exp = template_explanation(d)
    assert exp["source"] == "template"
    assert G.check_explanation(exp["text"], allowed_numbers_for(build_payload(d))) == []


class _FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResp:
    stop_reason = "end_turn"

    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeClient:
    def __init__(self, text):
        self.messages = self
        self._text = text

    def create(self, **kw):
        assert kw["model"] and kw["system"]
        return _FakeResp(self._text)


def test_ai_output_with_forbidden_falls_back_to_template():
    exp, problems = explain(_detail(), use_ai=True, client=_FakeClient("해킹 확률이 높은 곳입니다. 조심하세요."))
    assert exp["source"] == "template" and problems


def test_ai_output_with_unknown_number_falls_back():
    exp, problems = explain(_detail(), use_ai=True,
                            client=_FakeClient("이곳은 30점입니다. 작년에 사고가 57건 있었습니다. 조심하세요."))
    assert exp["source"] == "template" and any("수치" in p for p in problems)


def test_ai_output_valid_is_used():
    text = "샘플 정류장의 위험요인 점수는 30점입니다. SSID가 개방형 목록에 있어 보안접속이 되지 않습니다. 보안접속 SSID가 보이면 그쪽으로 연결하세요."
    exp, problems = explain(_detail(), use_ai=True, client=_FakeClient(text))
    assert exp["source"] == "ai" and problems == []
