"""Vercel 진입점 — FastAPI 프리셋이 이 파일의 `app`을 찾는다(api/ 폴더는 함수로 나뉘지 않음, requests #41).
로컬 실행은 그대로: uvicorn api.main:app --port 8000

[이 파일이 하는 일]
  Vercel(웹 서비스를 인터넷에 올려 주는 호스팅 서비스)은 backend/app.py 안의 `app`을 찾아 API 서버로 실행한다.
  실제 서버는 api/main.py에서 만들고, 이 파일은 그것을 불러와 이름만 노출하는 '입구' 역할이다.
"""
from api.main import app  # noqa: F401
