"""(선택) SSID 라벨 후보 생성 → data/interim/ssid_label_candidates.csv (plan.md §8.3-2)

※ 후보일 뿐이다. config/ssid_labels.csv에는 절대 쓰지 않는다. 확정은 사람이 근거를 확인한 뒤 한다.
실행: python pipeline/ai_label_assist.py [--top 100]
"""
import argparse
import json
import os

import _bootstrap  # noqa: F401
import pandas as pd

from wifisafe.io import INTERIM_DIR, write_csv

MODEL = os.environ.get("AI_MODEL", "claude-haiku-5-5")
SYSTEM = """너는 공공와이파이 SSID 이름만 보고 '개방형(open, 비밀번호 없는 접속)'인지 '보안접속(secure, 암호화 접속)'인지
후보 라벨을 제안한다. 이름만으로 판단할 수 없으면 반드시 unknown으로 둔다. 추측으로 확정하지 않는다.
입력 JSON 배열의 각 SSID에 대해 [{"ssid": ..., "label": "open|secure|unknown", "reason": "한 문장"}] JSON 배열만 출력한다."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=100)
    args = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(".env에 ANTHROPIC_API_KEY가 없습니다 (이 단계는 선택입니다)")
    census = pd.read_csv(INTERIM_DIR / "ssid_census.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    todo = census[census["current_status"] != "confirmed"].head(args.top)
    import anthropic
    client = anthropic.Anthropic()
    out = []
    for i in range(0, len(todo), 25):
        batch = todo.iloc[i:i + 25][["ssid", "rows", "example_provider"]].to_dict(orient="records")
        resp = client.messages.create(model=MODEL, max_tokens=8000, output_config={"effort": "low"}, system=SYSTEM,
                                      messages=[{"role": "user", "content": json.dumps(batch, ensure_ascii=False)}])
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        start, end = text.find("["), text.rfind("]")
        try:
            items = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            print(f"  배치 {i // 25}: JSON 파싱 실패 — 건너뜀")
            continue
        for it in items:
            if it.get("label") not in ("open", "secure", "unknown"):
                it["label"] = "unknown"
            out.append({"ssid": it.get("ssid", ""), "label": it["label"], "evidence": f"AI 후보: {it.get('reason', '')}",
                        "reviewer": "", "reviewed_at": "", "status": "candidate"})
    path = INTERIM_DIR / "ssid_label_candidates.csv"
    write_csv(path, pd.DataFrame(out))
    print(f"[ai_label_assist] 후보 {len(out)}건 → {path}  (사람이 검토 후 config/ssid_labels.csv에 옮기고 status=confirmed)")


if __name__ == "__main__":
    main()
