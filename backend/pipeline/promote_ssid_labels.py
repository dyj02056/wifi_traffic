"""검토 끝난 후보를 config/ssid_labels.csv로 옮긴다.

[이 파일이 하는 일]
  SSID 분류 작업의 마지막 단계입니다. 사람이 후보표(ssid_labels_candidates.csv)를 검토하며
  확정한 행(status=confirmed, 검토자·검토일 기입)만 실제 분류표(ssid_labels.csv)로 옮깁니다.
  옮긴 뒤 "SSID가 있는 행의 몇 %가 확정 분류로 덮였는지"를 출력합니다(목표 95%).

[SSID 분류 작업 순서] census.py → draft_ssid_labels.py(또는 ai_label_assist.py) → 사람이 검토 → ★ promote_ssid_labels.py

config/ssid_labels_candidates.csv에서 사람이 status=confirmed로 바꾸고 reviewer·reviewed_at을 채운 행만 옮긴다.
이미 ssid_labels.csv에 있는 SSID는 후보 쪽 값으로 갱신한다. status가 candidate인 행은 건드리지 않는다.

실행: python pipeline/promote_ssid_labels.py
"""
import _bootstrap  # noqa: F401
import pandas as pd

from wifisafe.io import CONFIG_DIR, write_csv

COLS = ["ssid", "label", "evidence", "reviewer", "reviewed_at", "status"]


def main():
    cand = pd.read_csv(CONFIG_DIR / "ssid_labels_candidates.csv", dtype=str, keep_default_na=False,
                       encoding="utf-8-sig")
    ok = cand[cand["status"].str.strip() == "confirmed"].copy()
    bad_label = ok[~ok["label"].isin(["open", "secure", "unknown"])]
    no_reviewer = ok[(ok["reviewer"].str.strip() == "") | (ok["reviewed_at"].str.strip() == "")]
    if len(bad_label) or len(no_reviewer):
        raise SystemExit(f"확정 행 오류 — label 값 이상 {bad_label['ssid'].tolist()[:10]}, "
                         f"reviewer/reviewed_at 비어 있음 {no_reviewer['ssid'].tolist()[:10]}")
    cur = pd.read_csv(CONFIG_DIR / "ssid_labels.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    # 기존 분류표에서 이번에 확정한 SSID를 빼고, 확정 행을 새로 붙인다(= 같은 SSID는 새 값으로 바뀜)
    merged = pd.concat([cur[~cur["ssid"].isin(ok["ssid"])], ok[COLS]], ignore_index=True)
    write_csv(CONFIG_DIR / "ssid_labels.csv", merged[COLS])
    rows = pd.to_numeric(cand["rows"]).sum()
    covered = pd.to_numeric(cand.loc[cand["ssid"].isin(merged.loc[merged["status"] == "confirmed", "ssid"]), "rows"]).sum()
    print(f"[promote_ssid_labels] 확정 {len(ok)}건 반영 → config/ssid_labels.csv 총 {len(merged)}건")
    print(f"  SSID 있는 행 기준 확정 커버리지 {covered / rows:.1%} (목표 95%)")


if __name__ == "__main__":
    main()
