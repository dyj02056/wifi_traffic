"""채점 결과 → 번들 문서 입력 조립. export_bundle(파일)과 daily_sync(DB)가 같은 조립을 쓴다."""
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
    docs_kwargs: dict                       # bundle.bundle_docs(**docs_kwargs)
    r1_status: dict
    bundle_r1_confirmed: bool
    warnings: list[str] = field(default_factory=list)


def assemble(scored: pd.DataFrame, region_ids: list[str], default_region_id: str, *, mode: str, snapshot: str,
             snapshot_dates: list[str], changes: pd.DataFrame, explanations: dict | None = None,
             background: dict | None = None) -> Assembled:
    """background를 넘기면 그것을 쓰고(예: DB에 있던 것), 없으면 config/sources.yaml 차트 정의로 만든다."""
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
    src_cfg = read_yaml(CONFIG_DIR / "sources.yaml")["sources"]
    d1 = src_cfg["D1"]
    sources = [{"id": "D1", "name": d1["name"], "dataset_id": d1["dataset_id"], "url": d1["url"],
                "retrieved_at": snapshot}]
    for sid in ("D3", "D4", "D5"):
        s = src_cfg.get(sid) or {}
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
