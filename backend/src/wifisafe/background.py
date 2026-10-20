"""배경 통계(점수 미반영). 이 모듈은 scoring·rules에서 import하면 안 된다(test_isolation.py)."""
from __future__ import annotations

import pandas as pd

from wifisafe.io import BACKEND_DIR, CONFIG_DIR, read_csv_any, read_json, read_yaml

NOTICE = "이 통계는 지점 점수에 반영하지 않습니다"


def build_background() -> tuple[dict, list[str]]:
    """sources.yaml의 background_charts 정의로 background.json을 만든다. 반환: (json, 경고 목록)."""
    cfg = read_yaml(CONFIG_DIR / "sources.yaml")
    sources = cfg.get("sources") or {}
    datasets, warnings = [], []
    for chart in cfg.get("background_charts") or []:
        src = sources.get(chart["source"])
        if not src:
            warnings.append(f"{chart['id']}: 알 수 없는 source {chart['source']}")
            continue
        path = BACKEND_DIR / src["file"]
        if not path.exists():
            warnings.append(f"{chart['id']}: 파일 없음 {path}")
            continue
        sidecar = path.with_suffix(".meta.json")
        retrieved = src.get("retrieved_at") or (read_json(sidecar).get("retrieved_at") if sidecar.exists() else None)
        if not retrieved:
            warnings.append(f"{chart['id']}: {chart['source']} retrieved_at 없음 → 출처 날짜 없는 통계는 렌더링하지 않음")
            continue
        df, _ = read_csv_any(path)
        for c in (chart["label_column"], chart["value_column"]):
            if c not in df.columns:
                raise SystemExit(f"{chart['id']}: 컬럼 '{c}' 없음. 실제 컬럼: {list(df.columns)}")
        gcol = chart.get("group_column")
        values = pd.to_numeric(df[chart["value_column"]].str.replace(",", ""), errors="coerce")
        series = [{"label": str(lbl), "value": float(v), "group": (str(df[gcol].iloc[i]) if gcol else None)}
                  for i, (lbl, v) in enumerate(zip(df[chart["label_column"]], values)) if pd.notna(v)]
        datasets.append({
            "id": chart["id"], "title": chart["title"], "unit": chart.get("unit", ""),
            "note": chart.get("note"),
            "source": {"name": src["name"], "dataset_id": src.get("dataset_id"), "url": src["url"],
                       "published_at": None, "retrieved_at": str(retrieved)},
            "series": series,
        })
    return {"included_in_score": False, "notice": NOTICE, "datasets": datasets}, warnings
