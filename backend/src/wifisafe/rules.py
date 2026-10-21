"""R1~R8 위험비율(r_i, 0~1) 판정 (plan.md §8.2). 가중치·임계값은 config/rules.py PARAMS에서만 읽는다.

[이 파일이 하는 일]
  와이파이 지점 하나하나를 보고, 위험요인 8가지(R1~R8) 각각에 대해
  "얼마나 위험한가"를 0(전혀 아님) ~ 1(최대) 사이 숫자로 판정합니다. 이 숫자를 '위험비율'이라고 부릅니다.
  최종 점수는 scoring.py가 이 위험비율에 가중치를 곱해서 계산합니다.

[전체 흐름에서의 위치]
  원본 데이터 → clean(정제) → ★ 여기서 요인별 위험비율 판정 → scoring.py(점수 합산) → 화면

[함수가 돌려주는 값]
  각 함수는 정규화된 DataFrame(clean.py 출력 컬럼)을 받아 (ratio, reason, flag) 세 Series를 돌려준다.
    - ratio: 위험비율(0~1)
    - reason: 사람이 읽는 판정 이유 문장 (지점 상세 화면에 그대로 표시됨)
    - flag: 데이터에 문제가 있을 때 붙이는 짧은 표식. 빈 문자열이면 없음.
  ※ DataFrame은 엑셀 표처럼 행·열로 된 데이터, Series는 그 표의 '한 열'이라고 생각하면 됩니다.
  R5(밀집도)는 주변 지점과 거리 계산이 필요해서 density.py에서 따로 계산한다.

  이 모듈은 background 모듈을 import하지 않는다.
  (background = 범죄·해킹 통계. 통계가 점수에 섞이지 않도록 일부러 분리해 둠)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.rules import PARAMS

# SSID 라벨 → 위험비율. 개방형(open, 비밀번호 없음)은 1.0, 보안접속(secure)은 0.0.
# 'unknown'(불명)은 여기 없으므로 아래에서 가정값(0.5)으로 채워진다.
LABEL_RATIO = {"open": 1.0, "secure": 0.0}
# 사실상 '값이 없다'는 뜻으로 쓰이는 표현들. 이런 값은 빈칸과 똑같이 취급한다.
MISSING_TOKENS = {"", "미상", "기타", "없음", "-", "nan", "none", "null"}
# 정부(과기정통부·NIA) 공공와이파이의 일반접속 SSID 'Public WiFi Free'만 적힌 칸. 같은 공유기가 보안접속
# 'Public WiFi Secure'를 함께 송출하는데 지자체마다 SSID 칸에 둘 다 적거나 Free만 적어서(전국 Free만 20,597행 / 둘 다 2,159행)
# 개방형으로 단정하지 않고 불명(가정 0.5)으로 본다 (docs/requests.md #47)
# 아래 패턴은 공백·밑줄·하이픈·점을 찾아 지우는 데 쓴다. ("Public_WiFi-Free" → "publicwififree")
_FREE_ONLY_NORM = re.compile(r"[\s_\-\.]+")


def gov_free_only(ssid: pd.Series) -> pd.Series:
    """SSID 칸에 정부 공공와이파이 'Free'만 적혀 있고 'Secure'는 없는 행이면 True.

    예) "Public WiFi Free" → True,  "Public WiFi Free, Public WiFi Secure" → False
    대소문자·띄어쓰기·기호 차이를 무시하려고 먼저 소문자로 바꾸고 기호를 지운 뒤 비교한다.
    """
    n = ssid.fillna("").astype(str).str.lower().str.replace(_FREE_ONLY_NORM, "", regex=True)
    return n.str.contains("publicwififree", regex=False) & ~n.str.contains("secure", regex=False)


# 올바른 전화번호 모양(기호를 지운 숫자만). 예) 0212345678(지역번호), 01012345678, 15881234(대표번호)
TEL_RE = re.compile(r"^(0\d{1,2}\d{3,4}\d{4}|1\d{3}\d{4})$")


@dataclass
class RuleTables:
    """채점에 필요한 사람이 확정한 표. 실데이터는 config/ 파일에서, mock은 생성기에서 넣는다.

    (mock = 테스트·시연용으로 만든 가짜 데이터)
    """
    ssid_labels: dict          # ssid -> open|secure|unknown  (와이파이 이름별 보안 분류)
    facility_map: dict         # facility_type -> (ratio, reason)  (시설 종류별 위험비율과 이유)
    outdoor_keywords: tuple    # '실외'로 볼 단어 목록 (예: 공원, 광장)
    indoor_override_keywords: tuple = ()  # 실외 단어가 있어도 이 단어가 있으면 실내로 본다 (예: 실내)


def _blank(s: pd.Series) -> pd.Series:
    """값이 비어 있거나 '미상'·'없음'처럼 사실상 빈 값이면 True."""
    return s.fillna("").astype(str).str.strip().str.lower().isin(MISSING_TOKENS)


def r1_secure_access(df: pd.DataFrame, t: RuleTables):
    """R1 보안접속 미지원 — 와이파이 이름(SSID)이 보안접속 목록에 있는지 본다.

    판정: 개방형 목록 → 1.0, 보안접속 목록 → 0.0, 불명·목록에 없음·SSID 빈칸 → 가정값 0.5
    """
    empty = df["ssid"].fillna("").astype(str).str.strip().eq("")
    # SSID를 라벨표에서 찾아 open/secure/unknown을 붙인다. SSID가 빈 행은 라벨 없음(NaN)으로 둔다.
    label = df["ssid"].map(t.ssid_labels).where(~empty)
    ratio = label.map(LABEL_RATIO).fillna(PARAMS["R1_UNKNOWN_RATIO"]).astype(float)
    free_only = gov_free_only(df["ssid"]) & label.eq("unknown")
    # np.select: 조건 목록을 위에서부터 차례로 검사해 처음 맞는 조건의 문장을 고른다. 아무것도 안 맞으면 마지막 기본값.
    reason = np.select(
        [empty, label.eq("open"), label.eq("secure"), free_only, label.eq("unknown")],
        ["SSID 정보 없음(가정 비율 적용)", "SSID가 개방형 목록에 있음", "SSID가 보안접속 목록에 있음",
         "정부 공공와이파이 일반접속(Free) SSID만 기재 — 보안접속(Secure) 함께 송출 여부 확인 불가(가정 비율 적용)",
         "SSID 분류 불명(가정 비율 적용)"],
        "SSID가 라벨 목록에 없음(가정 비율 적용)")
    flag = np.select([empty, label.isna(), free_only, label.eq("unknown")],
                     ["R1_ssid_missing", "R1_unlabeled", "R1_free_only", "R1_unknown"], "")
    return ratio, pd.Series(reason, index=df.index), pd.Series(flag, index=df.index)


def r2_facility(df: pd.DataFrame, t: RuleTables):
    """R2 시설유형 — 설치된 시설 종류(버스정류장, 관공서 등)에 따라 위험비율을 정한다.

    시설 종류별 비율은 config/facility_map.csv에 사람이 정해 둔 값을 쓴다. 표에 없는 종류는 가정값 0.5.
    """
    fac = df["facility_type"].fillna("").astype(str).str.strip()
    hit = fac.map(lambda v: t.facility_map.get(v))   # 표에서 찾은 (비율, 이유) 또는 None
    ratio = hit.map(lambda x: x[0] if x else PARAMS["R2_UNMAPPED_RATIO"]).astype(float)
    reason = [f"시설구분 '{f}': {x[1]}" if x else f"시설구분 '{f}' 미등록(가정 비율 적용)" for f, x in zip(fac, hit)]
    flag = hit.map(lambda x: "" if x else "R2_unmapped")
    return ratio, pd.Series(reason, index=df.index), flag


def r3_outdoor(df: pd.DataFrame, t: RuleTables):
    """R3 실외 — 설치장소 설명에 '공원', '광장' 같은 실외 단어가 있으면 1.0, 없으면 0.0.

    단, '실내' 같은 실내 단어가 함께 있으면 실외로 보지 않는다(0.0).
    """
    # 설치장소 상세 문구와 시설구분을 이어 붙여 한 문장으로 만든 뒤 단어를 찾는다.
    text = (df["place_detail"].fillna("").astype(str) + " " + df["facility_type"].fillna("").astype(str))
    ratios, reasons = [], []
    for s in text:
        # 목록에서 문장에 들어 있는 첫 번째 단어를 찾는다(없으면 None).
        kw = next((k for k in t.outdoor_keywords if k in s), None)
        indoor = next((k for k in t.indoor_override_keywords if k in s), None)
        if kw and not indoor:
            ratios.append(1.0)
            reasons.append(f"설치장소 문구에 실외 키워드 '{kw}' 포함")
        else:
            ratios.append(0.0)
            reasons.append("설치장소 문구에 실외 키워드 없음" if not kw else f"실내 키워드 '{indoor}' 함께 있음")
    empty = pd.Series("", index=df.index)   # R3은 따로 붙일 flag가 없다
    return pd.Series(ratios, index=df.index), pd.Series(reasons, index=df.index), empty


def parse_install_ym(v: str) -> tuple[pd.Timestamp | None, bool]:
    """'2017-03', '201703', '2017.03', '2017' → (Timestamp, year_only).

    설치연월은 지자체마다 적는 모양이 제각각이라 숫자만 뽑아서 해석한다.
    - 돌려주는 값: (날짜, 연도만 있었는지 여부). 해석할 수 없으면 (None, False).
    - 연도만 있으면 그해 1월 1일로 본다. 1990~2100년 밖의 값은 잘못된 값으로 보고 버린다.
    """
    digits = re.sub(r"\D", "", str(v or ""))   # 숫자가 아닌 글자를 모두 지운다
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
    """R4 노후도 — 설치 후 몇 년이 지났는지로 위험비율을 정한다.

    계산: 경과 연수 ÷ 8년(R4_FULL_YEARS), 최대 1.0. 예) 4년 경과 → 0.5, 10년 경과 → 1.0
    ref_date는 '오늘'로 간주할 기준 날짜(데이터를 받은 날)다. 설치연월이 없으면 가정값 0.5.
    """
    ratios, reasons, flags = [], [], []
    for v in df["install_ym"]:
        ts, year_only = parse_install_ym(v)
        if ts is None:
            ratios.append(PARAMS["R4_MISSING_RATIO"])
            reasons.append("설치연월 정보 없음(가정 비율 적용)")
            flags.append("R4_missing")
            continue
        # 일수를 365.25(윤년 포함 1년 평균 일수)로 나눠 연수로 바꾼다. 미래 날짜면 0으로 본다.
        years = max((ref_date - ts).days / 365.25, 0.0)
        ratios.append(min(years / PARAMS["R4_FULL_YEARS"], 1.0))
        reasons.append(f"설치 후 약 {years:.1f}년 경과")
        flags.append("R4_year_only" if year_only else "")
    return (pd.Series(ratios, index=df.index, dtype=float), pd.Series(reasons, index=df.index),
            pd.Series(flags, index=df.index))


def r6_operator(df: pd.DataFrame):
    """R6 제공주체 불명 — 제공사·관리기관 칸이 비어 있는 개수로 판정.

    둘 다 있음 → 0.0, 하나 비어 있음 → 0.5, 둘 다 비어 있음 → 1.0
    """
    # 빈 칸이면 1, 아니면 0으로 바꿔서 더하면 '비어 있는 칸 수'(0~2)가 된다.
    miss = _blank(df["provider"]).astype(int) + _blank(df["manager"]).astype(int)
    ratio = miss.map({0: 0.0, 1: PARAMS["R6_PARTIAL_RATIO"], 2: 1.0}).astype(float)
    reason = miss.map({0: "제공사·관리기관 정보 있음", 1: "제공사·관리기관 중 하나가 비어 있음",
                       2: "제공사·관리기관 정보가 모두 비어 있음"})
    return ratio, reason, pd.Series("", index=df.index)


def normalize_tel(v: str) -> str:
    """전화번호에서 공백·하이픈·괄호·점을 지운다. 예) '(02) 123-4567' → '021234567'"""
    return re.sub(r"[\s\-().]", "", str(v or ""))


def r7_report_path(df: pd.DataFrame):
    """R7 신고경로 부재 — 문제가 생겼을 때 연락할 관리기관 전화번호가 제대로 있는지 본다.

    번호가 없거나 전화번호 모양이 아니면 1.0, 올바르면 0.0.
    """
    tel = df["manager_tel"].fillna("").astype(str)
    norm = tel.map(normalize_tel)
    missing = _blank(tel)
    valid = norm.map(lambda x: bool(TEL_RE.match(x)))
    # '~'는 '아님(not)', '|'는 '또는(or)', '&'는 '그리고(and)'를 뜻한다.
    ratio = (~valid | missing).astype(float)
    reason = np.select([missing, ~valid], ["관리기관 전화번호 없음", "관리기관 전화번호 형식 불일치"], "관리기관 전화번호 있음")
    flag = np.select([~missing & ~valid], ["R7_invalid_tel"], "")
    return ratio, pd.Series(reason, index=df.index), pd.Series(flag, index=df.index)


def r8_data_age(df: pd.DataFrame, ref_date: pd.Timestamp):
    """R8 데이터 노후 — 데이터 기준일자가 얼마나 오래됐는지 본다.

    180일 미만 → 0.0, 180일 이상 → 0.5, 365일 이상 또는 날짜 없음 → 1.0
    """
    raw = df["data_date"].fillna("").astype(str).str.strip()
    # 날짜 글자를 실제 날짜로 바꾼다. 해석이 안 되면 NaT(빈 날짜)가 된다.
    d = pd.to_datetime(raw.where(raw.ne("")), errors="coerce", format="mixed")
    days = (ref_date - d).dt.days
    ratio = np.select([d.isna(), days >= PARAMS["R8_STALE_DAYS"], days >= PARAMS["R8_WARN_DAYS"]],
                      [1.0, 1.0, PARAMS["R8_WARN_RATIO"]], 0.0)
    reason = [("데이터 기준일자 없음" if pd.isna(n) else f"데이터 기준일자 후 {int(n)}일 경과") for n in days]
    flag = np.where(d.isna(), "R8_missing", "")
    return (pd.Series(ratio, index=df.index, dtype=float), pd.Series(reason, index=df.index),
            pd.Series(flag, index=df.index))
