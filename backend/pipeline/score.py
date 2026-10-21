"""채점: 전국 정제 데이터 전체를 채점(R5 경계 판정 때문)하고, 지정 지역만 wifi_scored.csv로 낸다.

[이 파일이 하는 일]
  clean.py가 만든 정제 데이터를 읽어 모든 지점의 R1~R8 위험비율·점수·등급을 계산합니다(계산은 engine.score_frame).
  사람이 엑셀로 열어 볼 수 있는 CSV(칸 이름 일부를 한국어로)와, 다음 단계용 parquet 파일을 저장하고
  등급 분포·문제 표식(flag) 분포 요약을 score_report.json에 남깁니다.

[순서] clean.py → ★ score.py → export_bundle.py

출력: processed/wifi_scored.parquet (전국, export_bundle 입력)
      processed/wifi_scored.csv     (지정 지역, 없으면 전국) — R1~R8 비율·점수, 위험점수, 등급
APP_MODE=final 에서 ssid_labels.csv 미확정이면 에러로 종료 (R1 게이트).

실행: python pipeline/score.py [--sido 서울특별시 --sigungu 구로구 | --region 11-guro]
"""
import argparse

import _bootstrap  # noqa: F401
import pandas as pd

from regions_arg import add_region_args, resolve_regions
from wifisafe.engine import enforce_r1_gate, load_tables, score_frame
from wifisafe.io import INTERIM_DIR, PROCESSED_DIR, app_mode, read_json, write_csv, write_json

# CSV에 내보낼 칸 순서: 기본 정보 → 위험비율 r1~r8 → 요인별 점수 → 점수·등급·flag → 판정 이유
CSV_COLS = (["key", "region_id", "sido", "sigungu", "place_name", "place_detail", "facility_type", "ssid", "lat",
             "lng", "install_ym_norm", "provider", "manager", "manager_tel", "data_date_norm", "address",
             "open_ap_within_radius"]
            + [f"r{i}" for i in range(1, 9)] + [f"R{i}_points" for i in range(1, 9)]
            + ["score", "grade", "flags"] + [f"reason{i}" for i in range(1, 9)])


def main():
    ap = argparse.ArgumentParser()
    add_region_args(ap)
    args = ap.parse_args()
    mode = app_mode()
    tables, status = load_tables()
    enforce_r1_gate(mode, status)

    clean_path = PROCESSED_DIR / "wifi_clean.parquet"
    if not clean_path.exists():
        raise SystemExit("processed/wifi_clean.parquet 없음 → python pipeline/clean.py 먼저 실행")
    df = pd.read_parquet(clean_path)
    snap = read_json(INTERIM_DIR / "clean_report.json")["snapshot"]
    scored = score_frame(df, tables, pd.Timestamp(snap))
    scored.to_parquet(PROCESSED_DIR / "wifi_scored.parquet", index=False)

    ids = resolve_regions(scored, args)
    out = scored[scored["region_id"].isin(ids)] if ids else scored
    write_csv(PROCESSED_DIR / "wifi_scored.csv", out[CSV_COLS].rename(columns={"score": "위험점수", "grade": "등급"}))

    # 점검: 모든 위험비율이 0~1 안에 있는지 확인하고 요약 숫자를 만든다
    rcols = [f"r{i}" for i in range(1, 9)]
    rng_ok = bool(((out[rcols] >= 0) & (out[rcols] <= 1)).all().all())
    info = {"snapshot": snap, "app_mode": mode, "r1_confirmed": status["r1_confirmed"], "regions": ids or "ALL",
            "rows": int(len(out)), "r_in_range": rng_ok,
            "grade_counts": out["grade"].value_counts().to_dict(),
            "flag_counts": out["flags"].str.split(";").explode().replace("", pd.NA).dropna().value_counts().to_dict()}
    write_json(INTERIM_DIR / "score_report.json", info)
    print(f"[score] 기준일 {snap}, APP_MODE={mode}, R1 확정={status['r1_confirmed']}")
    if not status["r1_confirmed"]:
        print("  ⚠ ssid_labels.csv 미확정 → 개발용 점수(임시·무효)입니다")
    print(f"  대상 {', '.join(ids) if ids else '전국'}: {len(out):,}행, r_i∈[0,1]={rng_ok}")
    print(f"  등급 분포: {info['grade_counts']}")
    print(f"  flag 분포: {info['flag_counts']}")
    print(f"  출력: {PROCESSED_DIR / 'wifi_scored.csv'}")


if __name__ == "__main__":
    main()
