# [이 파일이 하는 일]
#   pytest(파이썬 테스트 도구)가 테스트 전에 자동으로 읽는 공용 설정 파일.
#   backend/, backend/src/, backend/pipeline/을 모듈 검색 경로에 넣어 테스트가 config·wifisafe·pipeline 코드를 불러올 수 있게 한다.
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for p in (BACKEND, BACKEND / "src", BACKEND / "pipeline"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
