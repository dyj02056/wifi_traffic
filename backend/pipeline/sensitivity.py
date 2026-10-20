"""민감도 분석: 기준 A(기본) vs 기준 B(R1=15) → processed/sensitivity_r1.csv + 요약 (plan.md §8.6)

실행: python pipeline/sensitivity.py --sigungu 구로구 [--sido 서울특별시] | --region 11-guro
"""
import argparse

import _bootstrap  # noqa: F401
import pandas as pd

from regions_arg import add_region_args, resolve_regions
from wifisafe import sensitivity as SE
from wifisafe.io import PROCESSED_DIR, write_csv, write_json


def main():
    ap = argparse.ArgumentParser()
    add_region_args(ap)
    args = ap.parse_args()
    path = PROCESSED_DIR / "wifi_scored.parquet"
    if not path.exists():
        raise SystemExit("processed/wifi_scored.parquet 없음 → python pipeline/score.py 먼저 실행")
    scored = pd.read_parquet(path)
    ids = resolve_regions(scored, args, required=True)
    frames, summaries = [], {}
    for rid in ids:
        rows, summary = SE.analyze(scored[scored["region_id"] == rid])
        frames.append(rows.assign(region_id=rid))
        summaries[rid] = summary
        print(f"[sensitivity] {rid}: {summary['count']}개 지점, 상위 {summary['top_n']} 겹침 {summary['top_overlap']}, "
              f"스피어만 {summary['spearman']}, 등급 이동 {summary['grade_moves']}건")
        top = rows.head(10)[["rank_A", "rank_B", "delta", "score_A", "score_B", "place_name"]].to_string(index=False)
        print("  상위 10 (기준 A):\n    " + top.replace("\n", "\n    "))
    write_csv(PROCESSED_DIR / "sensitivity_r1.csv", pd.concat(frames, ignore_index=True))
    write_json(PROCESSED_DIR / "sensitivity_r1_summary.json",
               {"scenario_b_weights": SE.weights_b(), "regions": summaries})
    print(f"  출력: {PROCESSED_DIR / 'sensitivity_r1.csv'}")


if __name__ == "__main__":
    main()
