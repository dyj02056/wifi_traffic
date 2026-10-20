# 모든 가중치·파라미터는 여기서만 정의한다. rules.json, 채점표, 슬라이더 기본값이 모두 여기서 나온다.
# (plan.md §8.1) 점수 로직 어디에도 숫자(30, 20, …)를 직접 쓰지 않는다.
from dataclasses import dataclass

CONTRACT_VERSION_FILE = "contracts/VERSION"

DISCLAIMER = "이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다."


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    max_points: int
    source_fields: tuple
    is_assumption: bool
    one_liner: str   # 발표 1줄 설명. 1줄로 못 쓰면 규칙 삭제(투명성 원칙)


RULES = (
    Rule("R1", "보안접속 미지원", 30, ("ssid",), False,
         "SSID가 팀이 확정한 보안접속 목록에 없으면 위험요인으로 본다"),
    Rule("R2", "시설유형", 20, ("facility_type",), True,
         "불특정 다수가 오가는 시설일수록 높게 본다"),
    Rule("R3", "실외", 10, ("place_detail", "facility_type"), True,
         "설치장소 문구에 실외 키워드가 있으면 위험요인으로 본다"),
    Rule("R4", "노후도", 15, ("install_ym",), True,
         "설치 후 오래될수록 장비 보안 수준이 낮을 수 있다고 가정한다"),
    Rule("R5", "개방형 AP 밀집도", 10, ("lat", "lng", "ssid"), False,
         "반경 100m 안 개방형 AP가 많을수록 위장 AP가 섞이기 쉽다"),
    Rule("R6", "제공주체 불명", 5, ("provider", "manager"), False,
         "제공사·관리기관 정보가 비어 있으면 위험요인으로 본다"),
    Rule("R7", "신고경로 부재", 5, ("manager_tel",), False,
         "관리기관 전화번호가 없거나 형식이 틀리면 위험요인으로 본다"),
    Rule("R8", "데이터 노후", 5, ("data_date",), False,
         "데이터 기준일자가 오래되면 운영 상태를 신뢰하기 어렵다"),
)

RULE_IDS = tuple(r.id for r in RULES)
DEFAULT_WEIGHTS = tuple(r.max_points for r in RULES)

# (min, max, label, emoji, color) — min ≤ score < max
GRADES = ((0, 30, "낮음", "🟢", "#2e9e5b"),
          (30, 60, "주의", "🟡", "#e0a800"),
          (60, 101, "높음", "🔴", "#d64545"))

PARAMS = {
    "R1_UNKNOWN_RATIO": 0.5,   # 가정
    "R1_REGION_COVERAGE_MIN": 0.9,  # 지역의 SSID 있는 행 중 확정 라벨 비율이 이 이상이면 '임시(무효)' 해제 (requests #23)
    "R2_UNMAPPED_RATIO": 0.5,  # 가정, facility_map.csv 미등록 값
    "R4_FULL_YEARS": 8,        # 가정
    "R4_MISSING_RATIO": 0.5,   # 가정, '결측' flag
    "R5_RADIUS_M": 100,
    "R5_FULL_COUNT": 5,
    "R6_PARTIAL_RATIO": 0.5,
    "R8_WARN_DAYS": 180,
    "R8_WARN_RATIO": 0.5,
    "R8_STALE_DAYS": 365,
    "MIN_SELECTED_RULES": 2,
    "LOW_MAXSUM_WARN": 30,
}

# 민감도 분석 기준 B: R1 가중치만 바꾼다 (plan §8.6)
SENSITIVITY_B_OVERRIDES = {"R1": 15}
SENSITIVITY_TOP_N = 20
