"""contracts/schemas와 일치하는 pydantic 응답 모델. 스키마를 바꾸면 여기도 함께 바꾸고 test_api.py로 확인한다."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Grade = Literal["낮음", "주의", "높음"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class RuleMeta(Strict):
    id: str
    name: str
    max_points: float
    is_assumption: bool
    source_fields: list[str]
    one_liner: str


class GradeMeta(Strict):
    min: float
    max: float
    label: Grade
    emoji: str
    color: str


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


class Sido(Strict):
    sido_code: str
    sido: str
    count: int


class LatLng(Strict):
    lat: float
    lng: float


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


class BreakdownItem(Strict):
    id: str
    name: str
    ratio: float
    points: float
    max_points: float
    is_assumption: bool
    reason: str


class Explanation(Strict):
    text: str
    source: Literal["ai", "template"]
    model: str | None
    generated_at: str


class ReportContact(Strict):
    manager: str | None
    tel: str | None


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


class SourceRef(Strict):
    name: str
    dataset_id: str | None = None
    url: str
    published_at: str | None = None
    retrieved_at: str


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


class ExplainResponse(Strict):
    key: str
    ai_available: bool
    cached: bool
    explanation: Explanation
    ai_rejected_reasons: list[str]
