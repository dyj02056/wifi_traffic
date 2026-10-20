import pandas as pd
import pytest

from wifisafe.background import chart_series

POLICE = pd.DataFrame({"연도": ["2025", "2025", "2024", "2024"], "구분": ["발생건수", "검거건수", "발생건수", "검거건수"],
                       "해킹_계정도용": ["1,854", "265", "1197", "161"], "해킹_단순침입": ["1135", "352", "1164", "217"]})
KISA = pd.DataFrame({"구분": ["신고 건수"], "2019년 상반기": ["238"], "2019년": ["418"], "2020년": ["603"], "2023년하반기": ["613"]})


def test_row_filter_and_value_columns_sorted_by_year():
    chart = {"id": "c", "row_filter": {"구분": "발생건수"}, "label_column": "연도",
             "value_columns": ["해킹_계정도용", "해킹_단순침입"], "group_names": {"해킹_계정도용": "계정도용"},
             "sort_by_label": True}
    assert chart_series(POLICE, chart) == [
        {"label": "2024", "value": 1197.0, "group": "계정도용"}, {"label": "2024", "value": 1164.0, "group": "해킹_단순침입"},
        {"label": "2025", "value": 1854.0, "group": "계정도용"}, {"label": "2025", "value": 1135.0, "group": "해킹_단순침입"}]


def test_wide_columns_keeps_only_matching_year_columns():
    chart = {"id": "k", "row_filter": {"구분": "신고 건수"}, "wide_columns": r"\d{4}년"}
    assert [(s["label"], s["value"]) for s in chart_series(KISA, chart)] == [("2019년", 418.0), ("2020년", 603.0)]


def test_missing_column_fails_loudly():
    with pytest.raises(SystemExit, match="없음"):
        chart_series(POLICE, {"id": "x", "label_column": "연도", "value_columns": ["해킹_없는칸"]})
