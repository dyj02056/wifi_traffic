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
        series = chart_series(df, chart)
        datasets.append({
            "id": chart["id"], "title": chart["title"], "unit": chart.get("unit", ""),
            "note": chart.get("note"),
            "source": {"name": src["name"], "dataset_id": src.get("dataset_id"), "url": src["url"],
                       "published_at": None, "retrieved_at": str(retrieved)},
            "series": series,
        })
    return {"included_in_score": False, "notice": NOTICE, "datasets": datasets}, warnings


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def chart_series(df: pd.DataFrame, chart: dict) -> list[dict]:
    """차트 정의 하나 → series. 원본 값은 바꾸지 않고 읽는 방식만 고른다.

    - row_filter: {컬럼: 값} — 그 값인 줄만 쓴다 (예: 구분=발생건수)
    - 기본: label_column 줄마다 value_column 값 하나 (group_column이 있으면 그 값을 group으로)
    - value_columns: [칸...] — 줄마다 여러 칸을 막대로 펼치고 칸 이름을 group으로 (group_names로 표시 이름 지정)
    - wide_columns: 정규식 — 연도가 칸으로 놓인 표. 맞는 칸 이름이 label, 그 칸 값이 value (row_filter 후 1줄이어야 함)
    - sort_by_label: true — label 오름차순 (연도 순서)
    """
    cid = chart["id"]

    def need(cols):
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise SystemExit(f"{cid}: 컬럼 {missing} 없음. 실제 컬럼: {list(df.columns)}")

    for col, val in (chart.get("row_filter") or {}).items():
        need([col])
        df = df[df[col].astype(str).str.strip() == str(val)]
    if chart.get("wide_columns"):
        import re
        pat = re.compile(chart["wide_columns"])
        cols = [c for c in df.columns if pat.fullmatch(c)]
        if len(df) != 1 or not cols:
            raise SystemExit(f"{cid}: wide_columns는 1줄·맞는 칸 1개 이상 필요 (줄 {len(df)}, 칸 {cols})")
        vals = _num(df.iloc[0][cols])
        series = [{"label": c, "value": float(v), "group": None} for c, v in vals.items() if pd.notna(v)]
    elif chart.get("value_columns"):
        need([chart["label_column"], *chart["value_columns"]])
        names = chart.get("group_names") or {}
        series = [{"label": str(lbl), "value": float(v), "group": names.get(c, c)}
                  for c in chart["value_columns"]
                  for lbl, v in zip(df[chart["label_column"]], _num(df[c])) if pd.notna(v)]
    else:
        need([chart["label_column"], chart["value_column"]])
        gcol = chart.get("group_column")
        series = [{"label": str(lbl), "value": float(v), "group": (str(df[gcol].iloc[i]) if gcol else None)}
                  for i, (lbl, v) in enumerate(zip(df[chart["label_column"]], _num(df[chart["value_column"]])))
                  if pd.notna(v)]
    if chart.get("sort_by_label"):
        series.sort(key=lambda s: s["label"])
    return series
