"""원본 CSV 헤더 → 내부 영문 키 매핑, 지점 key, region_id.

COLUMN_MAP은 실제 D1 CSV(무료와이파이정보.csv, 2026-10-20 수령, 94,166행·20컬럼) 헤더로 확정했다.
헤더가 바뀌면 validate_header()가 즉시 에러를 낸다.
"""
from __future__ import annotations

import hashlib
import re

COLUMN_MAP_STATUS = "confirmed"

# 원본 헤더(한글) → 내부 키
COLUMN_MAP = {
    "설치장소명": "place_name",
    "설치장소상세": "place_detail",
    "설치시도명": "sido",
    "설치시군구명": "sigungu",
    "설치시설구분명": "facility_type",
    "서비스제공사명": "provider",
    "와이파이SSID": "ssid",
    "설치연월": "install_ym",
    "소재지도로명주소": "road_address",
    "소재지지번주소": "jibun_address",
    "관리기관명": "manager",
    "관리기관전화번호": "manager_tel",
    "WGS84위도": "lat",
    "WGS84경도": "lng",
    "데이터기준일자": "data_date",
}
# 원본 고유 ID(2026-10-20 스냅샷 기준 중복 0·빈값 0). 지점 key = sha1("id:" + 관리번호) 앞 10자
ID_COLUMN: str | None = "관리번호"

# SSID는 필수가 아니다: 원본의 29%가 빈 SSID → R1 '불명'(가정 비율) + R1_ssid_missing flag
REQUIRED_INTERNAL = ("place_name", "sido", "sigungu", "lat", "lng")

# 시도명 → 행정표준코드 앞 2자리. 원본 표기가 다르면(예: '강원도') 아래 별칭에 추가한다.
SIDO_CODES = {
    "서울특별시": "11", "부산광역시": "26", "대구광역시": "27", "인천광역시": "28",
    "광주광역시": "29", "대전광역시": "30", "울산광역시": "31", "세종특별자치시": "36",
    "경기도": "41", "충청북도": "43", "충청남도": "44", "전라남도": "46",
    "경상북도": "47", "경상남도": "48", "제주특별자치도": "50",
    "강원특별자치도": "51", "전북특별자치도": "52",
    # 별칭
    "강원도": "51", "전라북도": "52",
}
MOCK_SIDO_CODE = "99"

# 원본에 있지만 공식 시도코드를 아직 확인하지 못한 시도명. clean 단계에서 제외하고 경고만 남긴다(2026-10-20 결정).
# 코드를 확인하면 SIDO_CODES에 추가하고 여기서 지운다. (docs/requests.md #11)
PENDING_SIDO = {"전남광주통합특별시"}


class HeaderMismatch(SystemExit):
    pass


def validate_header(columns) -> None:
    cols = [str(c).strip() for c in columns]
    missing = [k for k in list(COLUMN_MAP) + ([ID_COLUMN] if ID_COLUMN else []) if k not in cols]
    if missing:
        raise HeaderMismatch(
            "CSV 헤더가 COLUMN_MAP과 다릅니다. src/wifisafe/schema.py의 COLUMN_MAP을 실제 헤더로 고치세요.\n"
            f"  COLUMN_MAP에 있지만 CSV에 없는 컬럼: {missing}\n"
            f"  CSV 실제 헤더: {cols}")


def point_key(lat: float, lng: float, ssid: str, place_name: str, raw_id: str | None = None) -> str:
    """고유 ID가 없으면 sha1(round(lat,5), round(lng,5), ssid, place_name) 앞 10자 (plan.md §8.5)."""
    basis = f"id:{raw_id}" if raw_id else f"{round(float(lat), 5):.5f}|{round(float(lng), 5):.5f}|{ssid}|{place_name}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]


# ── region_id = {시도코드}-{시군구명 로마자 슬러그} ───────────────────
_CHO = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
_JUNG = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi",
         "yu", "eu", "ui", "i"]
_JONG = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t",
         "ng", "t", "t", "k", "t", "p", "t"]
_SUFFIXES = ("구", "시", "군")


def romanize(text: str) -> str:
    """국어의 로마자 표기법 근사(음운 변화 미반영). 슬러그 용도로만 쓴다."""
    out = []
    for ch in text:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out.append(_CHO[code // 588] + _JUNG[(code % 588) // 28] + _JONG[code % 28])
        elif ch.isascii() and ch.isalnum():
            out.append(ch.lower())
        else:
            out.append("-")
    return "".join(out)


def sigungu_slug(sigungu: str) -> str:
    parts = []
    for word in re.split(r"\s+", sigungu.strip()):
        if len(word) >= 2 and word.endswith(_SUFFIXES):
            word = word[:-1]
        parts.append(romanize(word))
    slug = re.sub(r"-+", "-", "-".join(parts)).strip("-")
    return slug or "unknown"


def sido_code(sido: str) -> str:
    code = SIDO_CODES.get(sido.strip())
    if code is None:
        raise SystemExit(f"시도코드 미등록 시도명: {sido!r} → src/wifisafe/schema.py SIDO_CODES에 추가하세요")
    return code


def make_region_id(sido: str, sigungu: str, code: str | None = None) -> str:
    return f"{code or sido_code(sido)}-{sigungu_slug(sigungu)}"
