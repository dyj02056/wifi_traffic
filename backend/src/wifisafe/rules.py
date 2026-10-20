"""R1~R8 위험비율(r_i, 0~1) 판정 (plan.md §8.2). 가중치·임계값은 config/rules.py PARAMS에서만 읽는다.

각 함수는 정규화된 DataFrame(clean.py 출력 컬럼)을 받아 (ratio, reason, flag) 세 Series를 돌려준다.
flag는 빈 문자열이면 없음. R5는 density.py에서 계산한다.
이 모듈은 background 모듈을 import하지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.rules import PARAMS

LABEL_RATIO = {"open": 1.0, "secure": 0.0}
MISSING_TOKENS = {"", "미상", "기타", "없음", "-", "nan", "none", "null"}
TEL_RE = re.compile(r"^(0\d{1,2}\d{3,4}\d{4}|1\d{3}\d{4})$")


@dataclass
class RuleTables:
    """채점에 필요한 사람이 확정한 표. 실데이터는 config/ 파일에서, mock은 생성기에서 넣는다."""
    ssid_labels: dict          # ssid -> open|secure|unknown
    facility_map: dict         # facility_type -> (ratio, reason)
    outdoor_keywords: tuple
    indoor_override_keywords: tuple = ()


def _blank(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.lower().isin(MISSING_TOKENS)


def r1_secure_access(df: pd.DataFrame, t: RuleTables):
    empty = df["ssid"].fillna("").astype(str).str.strip().eq("")
    label = df["ssid"].map(t.ssid_labels).where(~empty)
    ratio = label.map(LABEL_RATIO).fillna(PARAMS["R1_UNKNOWN_RATIO"]).astype(float)
    reason = np.select(
        [empty, label.eq("open"), label.eq("secure"), label.eq("unknown")],
        ["SSID 정보 없음(가정 비율 적용)", "SSID가 개방형 목록에 있음", "SSID가 보안접속 목록에 있음",
         "SSID 분류 불명(가정 비율 적용)"],
        "SSID가 라벨 목록에 없음(가정 비율 적용)")
    flag = np.select([empty, label.isna(), label.eq("unknown")], ["R1_ssid_missing", "R1_unlabeled", "R1_unknown"], "")
    return ratio, pd.Series(reason, index=df.index), pd.Series(flag, index=df.index)


def r2_facility(df: pd.DataFrame, t: RuleTables):
    fac = df["facility_type"].fillna("").astype(str).str.strip()
    hit = fac.map(lambda v: t.facility_map.get(v))
    ratio = hit.map(lambda x: x[0] if x else PARAMS["R2_UNMAPPED_RATIO"]).astype(float)
    reason = [f"시설구분 '{f}': {x[1]}" if x else f"시설구분 '{f}' 미등록(가정 비율 적용)" for f, x in zip(fac, hit)]
    flag = hit.map(lambda x: "" if x else "R2_unmapped")
    return ratio, pd.Series(reason, index=df.index), flag


def r3_outdoor(df: pd.DataFrame, t: RuleTables):
    text = (df["place_detail"].fillna("").astype(str) + " " + df["facility_type"].fillna("").astype(str))
    ratios, reasons = [], []
    for s in text:
        kw = next((k for k in t.outdoor_keywords if k in s), None)
        indoor = next((k for k in t.indoor_override_keywords if k in s), None)
        if kw and not indoor:
            ratios.append(1.0)
            reasons.append(f"설치장소 문구에 실외 키워드 '{kw}' 포함")
        else:
            ratios.append(0.0)
            reasons.append("설치장소 문구에 실외 키워드 없음" if not kw else f"실내 키워드 '{indoor}' 함께 있음")
    empty = pd.Series("", index=df.index)
    return pd.Series(ratios, index=df.index), pd.Series(reasons, index=df.index), empty


def parse_install_ym(v: str) -> tuple[pd.Timestamp | None, bool]:
    """'2017-03', '201703', '2017.03', '2017' → (Timestamp, year_only)."""
    digits = re.sub(r"\D", "", str(v or ""))
    try:
        if len(digits) >= 6:
            y, m = int(digits[:4]), int(digits[4:6])
            if 1990 <= y <= 2100 and 1 <= m <= 12:
                return pd.Timestamp(year=y, month=m, day=1), False
        elif len(digits) == 4:
            y = int(digits)
            if 1990 <= y <= 2100:
                return pd.Timestamp(year=y, month=1, day=1), True
    except ValueError:
        pass
    return None, False


def r4_age(df: pd.DataFrame, ref_date: pd.Timestamp):
    ratios, reasons, flags = [], [], []
    for v in df["install_ym"]:
        ts, year_only = parse_install_ym(v)
        if ts is None:
            ratios.append(PARAMS["R4_MISSING_RATIO"])
            reasons.append("설치연월 정보 없음(가정 비율 적용)")
            flags.append("R4_missing")
            continue
        years = max((ref_date - ts).days / 365.25, 0.0)
        ratios.append(min(years / PARAMS["R4_FULL_YEARS"], 1.0))
        reasons.append(f"설치 후 약 {years:.1f}년 경과")
        flags.append("R4_year_only" if year_only else "")
    return (pd.Series(ratios, index=df.index, dtype=float), pd.Series(reasons, index=df.index),
            pd.Series(flags, index=df.index))


def r6_operator(df: pd.DataFrame):
    miss = _blank(df["provider"]).astype(int) + _blank(df["manager"]).astype(int)
    ratio = miss.map({0: 0.0, 1: PARAMS["R6_PARTIAL_RATIO"], 2: 1.0}).astype(float)
    reason = miss.map({0: "제공사·관리기관 정보 있음", 1: "제공사·관리기관 중 하나가 비어 있음",
                       2: "제공사·관리기관 정보가 모두 비어 있음"})
    return ratio, reason, pd.Series("", index=df.index)


def normalize_tel(v: str) -> str:
    return re.sub(r"[\s\-().]", "", str(v or ""))


def r7_report_path(df: pd.DataFrame):
    tel = df["manager_tel"].fillna("").astype(str)
    norm = tel.map(normalize_tel)
    missing = _blank(tel)
    valid = norm.map(lambda x: bool(TEL_RE.match(x)))
    ratio = (~valid | missing).astype(float)
    reason = np.select([missing, ~valid], ["관리기관 전화번호 없음", "관리기관 전화번호 형식 불일치"], "관리기관 전화번호 있음")
    flag = np.select([~missing & ~valid], ["R7_invalid_tel"], "")
    return ratio, pd.Series(reason, index=df.index), pd.Series(flag, index=df.index)


def r8_data_age(df: pd.DataFrame, ref_date: pd.Timestamp):
    raw = df["data_date"].fillna("").astype(str).str.strip()
    d = pd.to_datetime(raw.where(raw.ne("")), errors="coerce", format="mixed")
    days = (ref_date - d).dt.days
    ratio = np.select([d.isna(), days >= PARAMS["R8_STALE_DAYS"], days >= PARAMS["R8_WARN_DAYS"]],
                      [1.0, 1.0, PARAMS["R8_WARN_RATIO"]], 0.0)
    reason = [("데이터 기준일자 없음" if pd.isna(n) else f"데이터 기준일자 후 {int(n)}일 경과") for n in days]
    flag = np.where(d.isna(), "R8_missing", "")
    return (pd.Series(ratio, index=df.index, dtype=float), pd.Series(reason, index=df.index),
            pd.Series(flag, index=df.index))
