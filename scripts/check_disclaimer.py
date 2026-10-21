"""세 앱의 화면 소스에 면책 배너가 있는지, 금지 표현이 없는지 검사한다 (plan.md §0-7, §13).

  - web-draft/*.html: 면책 문구 원문 포함
  - frontend/src/app/layout.tsx: DisclaimerBar 사용 (frontend가 있을 때만)
  - 화면 소스 전체: 금지 표현(면책 문구 속 부정형 제외) 없음
실행(저장소 루트에서): python scripts/check_disclaimer.py   → 실패 시 종료코드 1

[이 파일이 하는 일]
  "이 점수는 위험요인 지표입니다"라는 안내 문구가 모든 화면에 붙어 있는지, 그리고 화면 문구에
  오해를 부르는 금지 표현(config/keywords.yaml의 forbidden_phrases)이 섞이지 않았는지 자동으로 검사한다.
  코드 주석은 사용자에게 보이지 않으므로 검사 전에 지운다(strip_comments).
  ※ 줄 끝에 붙인 // 주석은 지우지 않으므로, 화면 코드의 주석에도 금지 표현을 쓰지 않는다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend" / "src")]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config.rules import DISCLAIMER  # noqa: E402
from wifisafe.guardrails import find_forbidden  # noqa: E402

SCREEN_GLOBS = ["web-draft/*.html", "web-draft/js/*.js", "frontend/src/**/*.tsx", "frontend/src/**/*.ts"]


def strip_comments(text: str) -> str:
    """HTML 주석(<!-- -->), 블록 주석(/* */), 줄 맨 앞의 // 주석을 지운다."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def main() -> int:
    problems, checked = [], 0
    for html in sorted((ROOT / "web-draft").glob("*.html")):
        checked += 1
        if DISCLAIMER not in html.read_text(encoding="utf-8"):
            problems.append(f"{html.relative_to(ROOT)}: 면책 문구 없음")
    layout = ROOT / "frontend" / "src" / "app" / "layout.tsx"
    if (ROOT / "frontend").exists():
        checked += 1
        if not layout.exists() or "DisclaimerBar" not in layout.read_text(encoding="utf-8"):
            problems.append("frontend/src/app/layout.tsx: DisclaimerBar 사용 없음")
    for pattern in SCREEN_GLOBS:
        for p in ROOT.glob(pattern):
            bad = find_forbidden(strip_comments(p.read_text(encoding="utf-8")))
            if bad:
                problems.append(f"{p.relative_to(ROOT)}: 금지 표현 {bad}")
    if problems:
        print("[check_disclaimer] 실패\n  " + "\n  ".join(problems))
        return 1
    print(f"[check_disclaimer] 통과 — 면책 배너 {checked}개 화면 확인, 금지 표현 0건"
          + ("" if (ROOT / "frontend").exists() else " (frontend/ 없음: Next.js 검사는 담당 B 생성 후 적용)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
