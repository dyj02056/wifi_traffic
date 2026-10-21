"""지점 특성별 행동수칙. 일반 보안수칙 문구만 쓰고 수치·사건을 지어내지 않는다.

[이 파일이 하는 일]
  지점 상세 화면의 '이렇게 이용하세요' 안내 문구를 고릅니다.
  등급별 수칙 1개 → 그 지점에서 점수가 높게 나온 위험요인별 수칙 → 누구에게나 해당하는 기본 수칙 순으로 모아
  중복을 빼고 최대 5개까지 보여 줍니다.
"""
from __future__ import annotations

# 모든 지점에 공통으로 붙는 기본 수칙
BASE_TIPS = (
    "로그인·결제 같은 민감한 작업은 모바일 데이터로 하세요",
    "주소창의 https와 자물쇠 표시를 확인한 뒤 개인정보를 입력하세요",
    "와이파이 자동 연결 기능을 꺼 두세요",
)

# 위험요인별 수칙 (R2는 시설 종류라 사용자가 할 행동이 없어 따로 두지 않음)
TIP_BY_RULE = {
    "R1": "같은 장소에 보안접속 SSID가 보이면 그쪽으로 연결하세요",
    "R3": "실외 공유기는 이름이 비슷한 가짜 AP가 섞이기 쉬우니 SSID 철자를 꼭 확인하세요",
    "R4": "접속 화면에서 앱 설치나 업데이트를 요구하면 즉시 연결을 끊으세요",
    "R5": "같은 이름의 와이파이가 여러 개 보이면 관리기관에 공식 SSID를 확인하세요",
    "R6": "운영 주체가 불분명한 와이파이에서는 계정 로그인을 피하세요",
    "R7": "이상 징후를 발견하면 한국인터넷진흥원 118 상담센터에 신고하세요",
    "R8": "공개 정보가 오래된 지점이므로 현장 안내문의 SSID와 일치하는지 확인하세요",
}

# 등급별 대표 수칙 (항상 맨 앞에 온다)
GRADE_TIP = {
    "높음": "가능하면 개인 핫스팟을 사용하고 민감한 작업은 하지 마세요",
    "주의": "금융·로그인은 모바일 데이터로 하고 자동 연결을 꺼 두세요",
    "낮음": "보안접속 SSID를 쓰고 로그인·결제 전 https를 확인하세요",
}

REPORT_TIP = "관리기관 연락처로 고장·이상 SSID를 알릴 수 있습니다"


def tips_for(breakdown: list[dict], grade: str, max_items: int = 5) -> list[str]:
    """점수 기여(points)가 큰 규칙 순으로 해당 수칙을 고른다.

    - breakdown: 요인별 점수 내역 (bundle.detail_record에서 만든 것)
    - grade: 지점 등급 ("낮음"/"주의"/"높음")
    """
    tips = [GRADE_TIP[grade]]
    # 점수가 큰 요인부터 차례로, 위험비율이 0보다 큰(= 실제로 해당하는) 요인의 수칙만 넣는다.
    for b in sorted(breakdown, key=lambda x: -x["points"]):
        if b["ratio"] > 0 and b["id"] in TIP_BY_RULE:
            tips.append(TIP_BY_RULE[b["id"]])
    for t in BASE_TIPS:
        tips.append(t)
    # 같은 문구가 두 번 나오지 않게 순서를 지키며 중복을 지운다.
    seen, out = set(), []
    for t in tips:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:max_items]
