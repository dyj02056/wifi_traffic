"""채점 결과 → 번들 문서 입력 조립. export_bundle(파일)과 daily_sync(DB)가 같은 조립을 쓴다.

[이 파일이 하는 일]
  채점이 끝난 표를 받아서, 화면용 JSON 파일 묶음('번들')을 만드는 데 필요한 재료를 한데 모읍니다.
  - 지역별 SSID 확정 상태 계산 (발표용 모드에서 미확정 지역이 있으면 중단)
  - 배경 통계·데이터 출처 목록·사례 카드 준비
  - meta.json(번들 전체 정보), regions.json(지역 목록) 내용 만들기
  실제 파일 쓰기는 bundle.py가, DB 저장은 db.py가 맡습니다.

[전체 흐름에서의 위치]
  engine.score_frame(채점) → ★ assemble(재료 조립) → bundle.bundle_docs(문서 생성) → 파일 또는 DB 저장
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from wifisafe import bundle as B
from wifisafe.background import build_background
from wifisafe.cases import load_cases
from wifisafe.engine import confirmed_ssids, enforce_r1_region_gate, r1_region_status
from wifisafe.io import CONFIG_DIR, read_yaml


@dataclass
class Assembled:
    """조립 결과 상자."""
    docs_kwargs: dict                       # bundle.bundle_docs(**docs_kwargs)  — 번들 생성 함수에 그대로 넘길 재료
    r1_status: dict                         # 지역별 (SSID 확정 상태, 확정 비율)
    bundle_r1_confirmed: bool               # 번들의 모든 지역이 '임시(무효)'가 아니면 True
    warnings: list[str] = field(default_factory=list)   # 배경 통계를 만들며 생긴 경고들


def assemble(scored: pd.DataFrame, region_ids: list[str], default_region_id: str, *, mode: str, snapshot: str,
             snapshot_dates: list[str], changes: pd.DataFrame, explanations: dict | None = None,
             background: dict | None = None) -> Assembled:
    """background를 넘기면 그것을 쓰고(예: DB에 있던 것), 없으면 config/sources.yaml 차트 정의로 만든다.

    - scored: 채점이 끝난 전국(또는 일부) 표
    - region_ids: 번들에 넣을 지역 목록, default_region_id: 화면을 처음 열 때 보여 줄 지역
    - mode: "dev"(개발) 또는 "final"(발표용), snapshot: 데이터를 받은 날짜
    - snapshot_dates: 지금까지 받은 스냅샷 날짜들, changes: 스냅샷 비교로 찾은 추가·삭제 목록
    - explanations: 미리 만들어 둔 자동 설명(없으면 템플릿 문장 사용)
    """
    # 요청한 지역이 실제 데이터에 있는지, 기본 지역이 목록에 들어 있는지 먼저 확인
    unknown = sorted(set(region_ids) - set(scored["region_id"]))
    if unknown:
        raise SystemExit(f"없는 region_id: {unknown}")
    if default_region_id not in region_ids:
        raise SystemExit(f"기본 지역 {default_region_id}가 번들 지역 목록에 없습니다")
    r1_status = r1_region_status(scored, confirmed_ssids())
    enforce_r1_region_gate(mode, r1_status, region_ids)
    # 화면은 지역별 r1_status를 쓴다. meta.r1_confirmed는 "번들의 모든 지역이 임시(무효)가 아님"(이전 계약 호환용)
    bundle_r1_confirmed = all(r1_status[r][0] != "provisional" for r in region_ids)

    warnings: list[str] = []
    if background is None:
        background, warnings = build_background()
    # 데이터 출처 목록 만들기. D1 = 공공와이파이 표준데이터(점수의 원본), D3~D5 = 배경 통계 출처
    src_cfg = read_yaml(CONFIG_DIR / "sources.yaml")["sources"]
    d1 = src_cfg["D1"]
    sources = [{"id": "D1", "name": d1["name"], "dataset_id": d1["dataset_id"], "url": d1["url"],
                "retrieved_at": snapshot}]
    for sid in ("D3", "D4", "D5"):
        s = src_cfg.get(sid) or {}
        # 배경 통계 중 이 출처 이름을 쓰는 것이 실제로 있을 때만 출처 목록에 넣는다.
        ds = next((d for d in background["datasets"] if d["source"]["name"] == s.get("name")), None)
        if ds:
            sources.append({"id": sid, "name": s["name"], "dataset_id": s.get("dataset_id"), "url": s["url"],
                            "retrieved_at": ds["source"]["retrieved_at"]})

    meta = B.meta_json(is_mock=False, r1_confirmed=bundle_r1_confirmed, app_mode=mode,
                       data_reference_date=scored["data_date_norm"].dropna().max(), snapshot_collected_at=snapshot,
                       snapshot_count=len(snapshot_dates), regions_in_bundle=region_ids, sources=sources)
    regions = B.regions_json(scored, set(region_ids), default_region_id, r1_status)
    kwargs = dict(meta=meta, regions=regions, scored=scored, region_ids=region_ids, changes=changes,
                  snapshots=snapshot_dates, background=background, cases=load_cases(), explanations=explanations)
    return Assembled(kwargs, r1_status, bundle_r1_confirmed, warnings)


def print_summary(tag: str, a: Assembled, scored: pd.DataFrame, region_ids: list[str], limit: int = 20) -> None:
    """조립 결과를 터미널에 요약 출력한다(지역별 지점 수·SSID 확정 상태·등급 분포 등). 지역은 앞 limit곳만."""
    kw = a.docs_kwargs
    print(f"[{tag}] r1_confirmed={a.bundle_r1_confirmed}  지역 {len(region_ids)}곳")
    for rid in region_ids[:limit]:
        sub = scored[scored["region_id"] == rid]
        st, cov = a.r1_status[rid]
        n_exp = len((kw["explanations"] or {}).get(rid, {}))
        print(f"  {rid}: 지점 {len(sub):,}개, R1 {st}" + (f"(확정 {cov:.1%})" if cov is not None else "")
              + f", 사전 생성 설명 {n_exp}개(나머지 템플릿), 등급 {sub['grade'].value_counts().to_dict()}")
    if len(region_ids) > limit:
        counts = pd.Series([a.r1_status[r][0] for r in region_ids]).value_counts().to_dict()
        print(f"  … 외 {len(region_ids) - limit}곳 (R1 상태 전체: {counts})")
    print(f"  스냅샷 {len(kw['snapshots'])}회, 배경 통계 {len(kw['background']['datasets'])}종, "
          f"사례 카드 {len(kw['cases']['cases'])}건")
    for w in a.warnings:
        print(f"  ⚠ 배경: {w}")
    if not a.bundle_r1_confirmed:
        print("  ⚠ SSID 라벨 확정 비율이 기준 미만인 지역이 있음 — 그 지역을 고르면 '임시(무효)' 워터마크가 표시됩니다")
