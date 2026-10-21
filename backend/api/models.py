"""contracts/schemas와 일치하는 pydantic 응답 모델. 스키마를 바꾸면 여기도 함께 바꾸고 test_api.py로 확인한다.

[이 파일이 하는 일]
  API가 주고받는 데이터의 '모양'을 클래스로 정의합니다. (pydantic: 데이터 모양을 검사해 주는 파이썬 도구)
  예를 들어 Point 클래스는 "지점 하나에는 key(글자), lat(숫자), r(숫자 목록)… 이 있어야 한다"는 뜻입니다.
  API가 응답을 보내기 전에 이 모양과 맞는지 자동으로 검사하고, /docs 화면에 API 설명서로도 표시됩니다.

[읽는 법]
  - `이름: str` → 글자, `int` → 정수, `float` → 소수, `bool` → 참/거짓, `list[...]` → 목록
  - `str | None` → 글자이거나 비어 있을 수 있음(None)
  - `Literal["a", "b"]` → 정해진 값 중 하나만 허용
※ 주의: 클래스에 설명 문자열(docstring)을 넣으면 API 설명서 내용이 바뀌므로, 설명은 # 주석으로만 단다.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

# 등급은 이 세 값 중 하나만 허용
Grade = Literal["낮음", "주의", "높음"]


# 모든 모델의 바탕. extra="forbid": 정의하지 않은 칸이 섞여 있으면 오류로 본다(오타·실수 방지).
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── meta.json: 번들 전체 정보 ─────────────────────────────────
# 데이터 출처 한 건 (D1 공공와이파이 표준데이터 등)
class SourceEntry(Strict):
    id: str
    name: str
    dataset_id: str | None
    url: str
    retrieved_at: str | None


class Meta(Strict):
    contract_version: str
    disclaimer: str
    is_mock: bool
    r1_confirmed: bool
    app_mode: Literal["dev", "final", "mock"]
    data_reference_date: str | None
    snapshot_collected_at: str | None
    snapshot_count: int
    generated_at: str
    regions_in_bundle: list[str]
    sources: list[SourceEntry]


# ── rules.json: 채점 규칙 ─────────────────────────────────────
# 위험요인 하나(R1~R8)의 설명
class RuleMeta(Strict):
    id: str
    name: str
    max_points: float
    is_assumption: bool
    source_fields: list[str]
    one_liner: str


# 등급 구간 하나 (min 이상 max 미만)
class GradeMeta(Strict):
    min: float
    max: float
    label: Grade
    emoji: str
    color: str


# 채점 수식을 글로 적은 것 (/rules 화면 표시용)
class Formula(Strict):
    score: str
    rounding: str
    grade: str
    errors: str
    low_maxsum_basis: str


class Rules(Strict):
    rules: list[RuleMeta]
    grades: list[GradeMeta]
    params: dict[str, float]
    formula: Formula


# ── regions.json: 지역 목록 ───────────────────────────────────
# 시도 하나 (번호·이름·지점 수)
class Sido(Strict):
    sido_code: str
    sido: str
    count: int


class LatLng(Strict):
    lat: float
    lng: float


# 시군구 하나. available: 번들에 지점 데이터가 들어 있는지, r1_status: SSID 확정 상태, bbox: 처음 화면 범위
class Region(Strict):
    region_id: str
    sido_code: str
    sido: str
    sigungu: str
    count: int
    available: bool
    r1_status: Literal["confirmed", "provisional", "no_ssid"]
    r1_coverage: float | None
    center: LatLng
    bbox: list[float]


class Regions(Strict):
    default_region_id: str
    sido: list[Sido]
    regions: list[Region]


# ── points/<지역>.json: 지도에 찍을 지점 ─────────────────────
# 지점 하나. r = 위험비율 8개(R1~R8), flags = 데이터 문제 표식
class Point(Strict):
    key: str
    name: str
    lat: float
    lng: float
    r: list[float]
    score: float
    grade: Grade
    flags: list[str]


class Points(Strict):
    region_id: str
    count: int
    points: list[Point]


# ── detail/<지역>.json: 지점 상세 ─────────────────────────────
# 채점에 쓴 원본 값(근거)
class Evidence(Strict):
    ssid: str | None
    facility_type: str | None
    place_detail: str | None
    install_ym: str | None
    provider: str | None
    manager: str | None
    manager_tel: str | None
    data_date: str | None
    address: str | None
    open_ap_within_radius: int | None


# 요인 하나의 점수 내역: 위험비율·받은 점수·최대 점수·판정 이유
class BreakdownItem(Strict):
    id: str
    name: str
    ratio: float
    points: float
    max_points: float
    is_assumption: bool
    reason: str


# 자동 설명문. source가 "ai"면 AI가, "template"이면 정해진 문장 틀로 만든 것
class Explanation(Strict):
    text: str
    source: Literal["ai", "template"]
    model: str | None
    generated_at: str


# 고장·이상 신고 연락처
class ReportContact(Strict):
    manager: str | None
    tel: str | None


# 지점 상세 전체
class Detail(Strict):
    key: str
    region_id: str
    name: str
    score: float
    grade: Grade
    evidence: Evidence
    breakdown: list[BreakdownItem]
    explanation: Explanation
    safety_tips: list[str]
    report_contact: ReportContact
    flags: list[str]


# ── changes/<지역>.json: 최근 추가·삭제 ───────────────────────
class Change(Strict):
    key: str
    change: Literal["added", "removed"]
    snapshot_from: str
    snapshot_to: str
    place_name: str | None
    ssid: str | None
    lat: float
    lng: float


class Changes(Strict):
    region_id: str
    snapshots: list[str]
    collection_count: int
    changes: list[Change]


# ── sensitivity/<지역>.json: 민감도 분석 (기준 A vs 기준 B) ──
# 비교할 기준 하나 (이름과 가중치 8개)
class Scenario(Strict):
    label: str
    weights: list[float]


class SensitivitySummary(Strict):
    count: int
    top_n: int
    top_overlap: int
    spearman: float | None
    grade_moves: int


class SensitivityRow(Strict):
    key: str
    place_name: str | None
    rank_A: int
    rank_B: int
    delta: int
    score_A: float
    score_B: float
    grade_A: Grade
    grade_B: Grade


class Sensitivity(Strict):
    region_id: str
    scenario_a: Scenario
    scenario_b: Scenario
    summary: SensitivitySummary
    rows: list[SensitivityRow]


# ── background.json · cases.json: 배경 통계·사례 (점수 미반영) ──
# 통계·사례의 출처 (published_at: 발행일, retrieved_at: 우리가 확인한 날)
class SourceRef(Strict):
    name: str
    dataset_id: str | None = None
    url: str
    published_at: str | None = None
    retrieved_at: str


# 차트의 막대 하나
class SeriesItem(Strict):
    label: str
    value: float
    group: str | None = None


class Dataset(Strict):
    id: str
    title: str
    unit: str
    note: str | None
    source: SourceRef
    series: list[SeriesItem]


# included_in_score는 항상 False여야 한다(통계를 점수에 넣지 않는다는 약속을 모양 검사로 강제)
class Background(Strict):
    included_in_score: Literal[False]
    notice: str
    datasets: list[Dataset]


class Case(Strict):
    id: str
    title: str
    summary: str
    principle: str
    related_rules: list[str]
    source: SourceRef


class Cases(Strict):
    label: str
    cases: list[Case]


# ── /explain 응답 ─────────────────────────────────────────────
# ai_available: AI 사용 가능 여부, cached: 미리 만든 설명을 썼는지, ai_rejected_reasons: AI 설명이 검사에 걸린 이유
class ExplainResponse(Strict):
    key: str
    ai_available: bool
    cached: bool
    explanation: Explanation
    ai_rejected_reasons: list[str]


# ── 회원·GPS (contracts 밖, API 전용 — docs/requests.md #18·#19) ─────
# 내 위치에서 가장 가까운 지역. method: DB 거리 계산(postgis) 또는 지역 중심점 비교(region_center)
class NearestResponse(Strict):
    region_id: str
    distance_m: float | None
    method: Literal["postgis", "region_center"]


# 구글 로그인 요청: 구글이 화면에 준 신분증(credential, ID 토큰)
class GoogleLogin(Strict):
    credential: str


# 네이버 로그인 요청: 네이버가 화면에 준 접근 토큰
class NaverLogin(Strict):
    access_token: str


# 회원 정보 (provider "dev"는 개발용 가짜 로그인)
class User(Strict):
    id: int
    provider: Literal["google", "naver", "dev"]
    display_name: str
    sido: str | None
    sigungu: str | None
    region_id: str | None


# 로그인 성공 응답: 출입증(token)과 회원 정보. needs_region이 True면 '사는 지역 선택' 화면을 띄운다
class AuthResponse(Strict):
    token: str
    user: User
    needs_region: bool


# 사는 지역 변경 요청 (둘 중 하나만 보낸다)
class RegionUpdate(Strict):
    region_id: str | None = None   # 시군구까지 고르면 region_id
    sido_code: str | None = None   # 시도만 고르면 sido_code (예: "41")


# 장소 검색 결과 한 건
class SearchHit(Strict):
    key: str
    region_id: str
    sido: str
    sigungu: str
    name: str
    address: str | None
    place_detail: str | None
    lat: float
    lng: float


# 장소 검색 응답. method: DB 검색(db) 또는 DB가 없을 때 이름만으로 찾은 것(names)
class SearchResponse(Strict):
    query: str
    method: Literal["db", "names"]
    hits: list[SearchHit]
