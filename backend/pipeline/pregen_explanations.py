"""시연 지역 AI 설명 사전 생성 → processed/explanations/{region_id}.json (plan.md §8.4, M5)

ANTHROPIC_API_KEY가 있으면 AI 설명을 만들고 가드레일(금지어·근거 외 수치·문장 수)을 통과한 것만 쓴다.
실패하거나 키가 없으면 템플릿. export_bundle.py가 이 파일을 detail에 합친다.
검수 리포트: processed/explanations/{region_id}.report.json (M5: 샘플 20건 금지어 0·근거 외 수치 0)

실행: python pipeline/pregen_explanations.py --region 11-guro [--limit 20] [--template-only]
"""
import argparse
import os

import _bootstrap  # noqa: F401
import pandas as pd

from regions_arg import add_region_args, resolve_regions
from wifisafe import guardrails
from wifisafe.bundle import detail_record
from wifisafe.explain import allowed_numbers_for, build_payload, explain
from wifisafe.io import PROCESSED_DIR, write_json


def main():
    ap = argparse.ArgumentParser()
    add_region_args(ap)
    ap.add_argument("--limit", type=int, help="앞에서부터 N개만(점수 높은 순)")
    ap.add_argument("--template-only", action="store_true")
    args = ap.parse_args()
    scored = pd.read_parquet(PROCESSED_DIR / "wifi_scored.parquet")
    ids = resolve_regions(scored, args, required=True)
    use_ai = (not args.template_only) and bool(os.environ.get("ANTHROPIC_API_KEY"))
    client = None
    if use_ai:
        import anthropic
        client = anthropic.Anthropic()
    else:
        print("ANTHROPIC_API_KEY 없음 또는 --template-only → 템플릿 설명만 생성")
    for rid in ids:
        sub = scored[scored["region_id"] == rid].sort_values(["score", "key"], ascending=[False, True])
        if args.limit:
            sub = sub.head(args.limit)
        out, report = {}, []
        for _, r in sub.iterrows():
            d = detail_record(r)
            exp, problems = explain(d, use_ai=use_ai, client=client)
            final_problems = guardrails.check_explanation(exp["text"], allowed_numbers_for(build_payload(d)))
            out[d["key"]] = exp
            report.append({"key": d["key"], "source": exp["source"], "ai_rejected_reasons": problems,
                           "final_text_problems": final_problems, "text": exp["text"]})
        write_json(PROCESSED_DIR / "explanations" / f"{rid}.json", out)
        n_ai = sum(1 for x in report if x["source"] == "ai")
        bad = [x for x in report if x["final_text_problems"]]
        forbidden = sum(1 for x in report if any("금지" in p for p in x["final_text_problems"]))
        unknown_num = sum(1 for x in report if any("수치" in p for p in x["final_text_problems"]))
        write_json(PROCESSED_DIR / "explanations" / f"{rid}.report.json", {
            "region_id": rid, "count": len(report), "ai": n_ai, "template": len(report) - n_ai,
            "final_forbidden": forbidden, "final_unknown_numbers": unknown_num, "items": report})
        print(f"[pregen] {rid}: {len(report)}건 (AI {n_ai}, 템플릿 {len(report) - n_ai}), "
              f"최종 금지어 {forbidden}건, 근거 외 수치 {unknown_num}건, 기타 문제 {len(bad) - forbidden - unknown_num}건")


if __name__ == "__main__":
    main()
