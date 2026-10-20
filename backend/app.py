"""Vercel 진입점 — FastAPI 프리셋이 이 파일의 `app`을 찾는다(api/ 폴더는 함수로 나뉘지 않음, requests #41).
로컬 실행은 그대로: uvicorn api.main:app --port 8000"""
from api.main import app  # noqa: F401
