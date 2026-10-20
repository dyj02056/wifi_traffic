"""SSID 라벨 후보 초안 — 이름만 보는 규칙 기반 분류 (AI 미사용) → config/ssid_labels_candidates.csv

※ 후보일 뿐이다. config/ssid_labels.csv에는 쓰지 않는다. 사람이 검토해 옮기고 status=confirmed로 확정한다.

한 칸의 SSID를 쉼표·슬래시·괄호로 나눈 '토큰'마다 판정한다.
  S  보안: 이름에 secure·보안 포함
  O  개방: 이름에 free·무료·프리 포함
  P  개방(짝 추정): 키워드는 없지만 같은 이름의 Secure 버전이 데이터에 따로 있음 (예: SEOUL ↔ SEOUL_Secure)
  D  장비명: 공유기 기본값·모델명으로 보임 (iptime, T750 등)
  U  불명
칸 단위 후보:
  S와 O/P가 함께 있으면 → secure, 신뢰도 '검토필요'(혼합: 보안접속을 고를 수 있는 지점) — 리드 결정 사항
  S만 → secure(높음) / O만 → open(높음) / O·P만 → open(중간) / U·D가 섞이면 한 단계 낮춤 / 전부 U·D → unknown

실행: python pipeline/draft_ssid_labels.py
"""
import re

import _bootstrap  # noqa: F401
import pandas as pd

from wifisafe.io import CONFIG_DIR, INTERIM_DIR, write_csv

SECURE_RE = re.compile(r"secure|보안", re.I)
FREE_RE = re.compile(r"free|무료|프리", re.I)
DEVICE_RE = re.compile(r"^(iptime|ipTIME|T\d{3}|ATM-|TVWS|mlte_|olleh)", re.I)
SPLIT_RE = re.compile(r"[,/()]|\.(?=[A-Za-z])")


def norm(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", s.lower())


def tokens(cell: str) -> list[str]:
    return [t.strip() for t in SPLIT_RE.split(cell) if t.strip()]


def classify_token(t: str, secure_bases: set[str]) -> str:
    if SECURE_RE.search(t):
        return "S"
    if FREE_RE.search(t):
        return "O"
    if DEVICE_RE.search(t):
        return "D"
    if norm(t) in secure_bases:
        return "P"
    return "U"


def classify(cell: str, secure_bases: set[str]):
    toks = tokens(cell)
    kinds = [classify_token(t, secure_bases) for t in toks]
    has = set(kinds)
    desc = ", ".join(f"{t}={k}" for t, k in zip(toks, kinds))
    if "S" in has and has & {"O", "P"}:
        return "secure", "검토필요", "MIXED", f"혼합: 개방형과 보안접속 SSID를 함께 제공 [{desc}] — 보안접속 선택 가능 지점을 secure로 볼지 리드 결정"
    if "S" in has:
        conf = "높음" if has == {"S"} else "중간"
        return "secure", conf, "SECURE_NAME", f"이름에 Secure/보안 포함 [{desc}]"
    if has & {"O", "P"}:
        if has <= {"O"}:
            conf = "높음"
        elif has <= {"O", "P"}:
            conf = "중간"
        else:
            conf = "낮음"
        rule = "FREE_NAME" if "O" in has else "PAIR_OF_SECURE"
        why = ("이름에 Free/무료 포함" if rule == "FREE_NAME"
               else "같은 이름의 Secure 버전이 데이터에 따로 있어 그 짝인 개방형으로 추정")
        return "open", conf, rule, f"{why} [{desc}]"
    if "D" in has:
        return "unknown", "낮음", "DEVICE_NAME", f"공유기 기본값·장비 모델명으로 보임 — 현장 확인 필요 [{desc}]"
    return "unknown", "낮음", "NO_KEYWORD", f"이름만으로 판단 불가 [{desc}]"


def main():
    census = pd.read_csv(INTERIM_DIR / "ssid_census.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    census = census[census["ssid"] != ""].copy()
    census["rows"] = census["rows"].astype(int)
    total = census["rows"].sum()
    all_tokens = {t for cell in census["ssid"] for t in tokens(cell)}
    secure_bases = {norm(SECURE_RE.sub("", t)) for t in all_tokens if SECURE_RE.search(t)} - {""}

    out = []
    for r in census.sort_values("rows", ascending=False).itertuples(index=False):
        label, conf, rule, evidence = classify(r.ssid, secure_bases)
        out.append({"ssid": r.ssid, "label": label, "evidence": evidence, "reviewer": "", "reviewed_at": "",
                    "status": "candidate", "confidence": conf, "rule": rule, "rows": r.rows,
                    "example_sigungu": r.example_sigungu})
    df = pd.DataFrame(out)
    df["cum_share_nonempty"] = (df["rows"].cumsum() / total).round(4)
    df.insert(0, "rank", range(1, len(df) + 1))
    path = CONFIG_DIR / "ssid_labels_candidates.csv"
    write_csv(path, df)

    top = df[df["cum_share_nonempty"].shift(fill_value=0) < 0.95]
    print(f"[draft_ssid_labels] SSID {len(df):,}개(빈값 제외 {total:,}행) 후보 → {path}")
    print(f"  상위 {len(top)}개가 SSID 있는 행의 95% 차지")
    for name, sub in (("전체", df), (f"상위 {len(top)}", top)):
        by_label = sub.groupby("label")["rows"].sum()
        by_conf = sub.groupby("confidence")["rows"].sum()
        print(f"  [{name}] 라벨별 행: " + ", ".join(f"{k} {v:,}({v / sub['rows'].sum():.1%})" for k, v in by_label.items()))
        print(f"  [{name}] 신뢰도별 행: " + ", ".join(f"{k} {v:,}" for k, v in by_conf.items()))


if __name__ == "__main__":
    main()
