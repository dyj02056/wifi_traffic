"""pipeline/ 스크립트가 config·wifisafe를 import할 수 있게 경로를 잡는다.

[이 파일이 하는 일]
  pipeline/ 폴더의 스크립트들은 맨 위에서 `import _bootstrap`을 한 줄 씁니다. 그러면 이 파일이 먼저 실행되어
  ① backend/와 backend/src/를 모듈 검색 경로에 넣고(그래야 `from wifisafe ...`, `from config ...`가 동작)
  ② 터미널 출력을 UTF-8로 맞춰 한글이 깨지지 않게 하고
  ③ backend/.env의 환경변수(DB 주소, API 키 등)를 불러옵니다.

[pipeline 폴더란]
  공공데이터를 내려받아 → 정제 → 채점 → 화면용 번들로 내보내는 '데이터 공장' 스크립트 모음입니다.
  하나씩 손으로 돌릴 수도 있고, daily_sync.py가 매일 자동으로 전체를 한 번에 돌리기도 합니다.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]   # backend/ 폴더
for p in (BACKEND, BACKEND / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# 윈도우 터미널은 기본 글자 방식이 달라 한글이 깨질 수 있어 UTF-8로 바꾼다
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from wifisafe.io import load_env  # noqa: E402

load_env()
