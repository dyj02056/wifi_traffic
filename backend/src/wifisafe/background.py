"""배경 통계(점수 미반영). 이 모듈은 scoring·rules에서 import하면 안 된다(test_isolation.py).

[이 파일이 하는 일]
  경찰청 해킹 발생 건수, KISA 침해사고 통계 같은 '참고용 배경 통계'를 차트용 JSON(background.json)으로 만듭니다.
  이 통계는 /context 화면에 보여 주기만 하고, 지점 점수에는 절대 넣지 않습니다.
  (지역 범죄 통계를 점수에 섞으면 '이 동네 와이파이가 위험하다'는 근거 없는 낙인이 될 수 있기 때문)

[동작 방식]
  config/sources.yaml의 background_charts 항목에 "어느 파일의 어느 칸을 어떤 차트로 그릴지"가 적혀 있고,
  이 파일은 그 정의대로 CSV를 읽어 차트 데이터(series)로 바꿉니다. 원본 숫자는 바꾸지 않습니다.
"""
from __future__ import annotations

import pandas as pd

from wifisafe.io import BACKEND_DIR, CONFIG_DIR, read_csv_any, read_json, read_yaml

# 배경 통계 화면에 항상 붙이는 안내 문구
NOTICE = "이 통계는 지점 점수에 반영하지 않습니다"


def build_background() -> tuple[dict, list[str]]:
    """sources.yaml의 background_charts 정의로 background.json을 만든다. 반환: (json, 경고 목록).

    출처 정보가 없거나, 파일이 없거나, 언제 받은 자료인지(retrieved_at) 모르면 그 차트는 건너뛰고 경고만 남긴다.
    """
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
        # 받은 날짜는 sources.yaml에 적혀 있거나, 같은 이름의 .meta.json 파일(사이드카)에 적혀 있다.
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
    """'1,234' 같은 글자를 숫자 1234로 바꾼다. 숫자가 아니면 빈 값(NaN)."""
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def chart_series(df: pd.DataFrame, chart: dict) -> list[dict]:
    """차트 정의 하나 → series. 원본 값은 바꾸지 않고 읽는 방식만 고른다.

    series는 차트의 막대 하나하나를 {"label": 가로축 이름, "value": 값, "group": 묶음 이름} 으로 적은 목록이다.

    - row_filter: {컬럼: 값} — 그 값인 줄만 쓴다 (예: 구분=발생건수)
    - 기본: label_column 줄마다 value_column 값 하나 (group_column이 있으면 그 값을 group으로)
    - value_columns: [칸...] — 줄마다 여러 칸을 막대로 펼치고 칸 이름을 group으로 (group_names로 표시 이름 지정)
    - wide_columns: 정규식 — 연도가 칸으로 놓인 표. 맞는 칸 이름이 label, 그 칸 값이 value (row_filter 후 1줄이어야 함)
    - sort_by_label: true — label 오름차순 (연도 순서)
    """
    cid = chart["id"]

    def need(cols):
        """필요한 칸이 표에 없으면 어떤 칸이 있는지 알려 주며 멈춘다."""
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise SystemExit(f"{cid}: 컬럼 {missing} 없음. 실제 컬럼: {list(df.columns)}")

    for col, val in (chart.get("row_filter") or {}).items():
        need([col])
        df = df[df[col].astype(str).str.strip() == str(val)]
    if chart.get("wide_columns"):
        # 연도가 칸 이름으로 가로로 놓인 표: 예) 칸 "2021","2022","2023" → 막대 3개
        import re
        pat = re.compile(chart["wide_columns"])
        cols = [c for c in df.columns if pat.fullmatch(c)]
        if len(df) != 1 or not cols:
            raise SystemExit(f"{cid}: wide_columns는 1줄·맞는 칸 1개 이상 필요 (줄 {len(df)}, 칸 {cols})")
        vals = _num(df.iloc[0][cols])
        series = [{"label": c, "value": float(v), "group": None} for c, v in vals.items() if pd.notna(v)]
    elif chart.get("value_columns"):
        # 한 줄에 여러 값 칸이 있는 표: 칸마다 다른 묶음(group)의 막대로 펼친다.
        need([chart["label_column"], *chart["value_columns"]])
        names = chart.get("group_names") or {}
        series = [{"label": str(lbl), "value": float(v), "group": names.get(c, c)}
                  for c in chart["value_columns"]
                  for lbl, v in zip(df[chart["label_column"]], _num(df[c])) if pd.notna(v)]
    else:
        # 기본: 한 줄 = 막대 하나
        need([chart["label_column"], chart["value_column"]])
        gcol = chart.get("group_column")
        series = [{"label": str(lbl), "value": float(v), "group": (str(df[gcol].iloc[i]) if gcol else None)}
                  for i, (lbl, v) in enumerate(zip(df[chart["label_column"]], _num(df[chart["value_column"]])))
                  if pd.notna(v)]
    if chart.get("sort_by_label"):
        series.sort(key=lambda s: s["label"])
    return series
