"""FastAPI — backend/dist/data 번들을 그대로 서빙 + /explain (plan.md §8.7).

[이 파일이 하는 일]
  화면(프론트엔드)이 데이터를 요청하면 JSON으로 답해 주는 'API 서버'를 만드는 시작점입니다.
  (API: 프로그램끼리 정해진 주소로 데이터를 주고받는 창구. 예) GET /points/41-goyang → 고양시 지점 목록)
  FastAPI는 파이썬으로 이런 서버를 쉽게 만들게 해 주는 도구입니다.
  실제 주소별 처리는 api/routes/ 폴더의 파일들에 나뉘어 있습니다.

[데이터를 어디서 읽나]
  DATABASE_URL이 있으면 Neon(bundle_docs)에서, 없으면 파일 번들(dist/data, 없으면 mock)에서 읽는다.
  BUNDLE_DIR 환경변수로 다른 파일 번들(예: ../contracts/mock)을 강제할 수 있다.

실행(backend/에서): uvicorn api.main:app --reload --port 8000   → http://localhost:8000/docs
배포: Vercel 파이썬 함수(backend/vercel.json) — docs/requests.md #17
"""
import os
import sys
import urllib.parse
from pathlib import Path

# backend/와 backend/src/를 파이썬이 모듈을 찾는 경로에 추가한다(그래야 config, wifisafe를 import할 수 있음).
BACKEND = Path(__file__).resolve().parents[1]
for p in (BACKEND, BACKEND / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.routes import bundle_routes, explain, user_routes  # noqa: E402
from api.store import BundleStore, DbStore  # noqa: E402
from config.rules import DISCLAIMER  # noqa: E402
from wifisafe.db import database_url  # noqa: E402
from wifisafe.io import DIST_DATA_DIR, MOCK_DIR, load_env  # noqa: E402

# 모든 응답의 머리말(header)에 안내 문구를 붙인다. 머리말에는 한글을 그대로 못 넣어서 %XX 모양으로 바꿔 둔다.
DISCLAIMER_HEADER = urllib.parse.quote(DISCLAIMER)


def _make_store(bundle_dir: Path | None):
    """명시한 파일 번들 > BUNDLE_DIR > DATABASE_URL(Neon) > dist/data > mock 순서.

    데이터를 꺼내 줄 '창고(store)'를 고른다. 돌려주는 값: (창고, 어디서 읽는지 설명 글자)
    """
    if bundle_dir is None and not os.environ.get("BUNDLE_DIR"):
        url = database_url(required=False)
        if url:
            return DbStore(url), "neon"
    root = Path(bundle_dir or os.environ.get("BUNDLE_DIR") or DIST_DATA_DIR)
    if not root.is_absolute():
        root = (BACKEND / root).resolve()
    if not (root / "meta.json").exists() and bundle_dir is None and not os.environ.get("BUNDLE_DIR"):
        print(f"⚠ 실데이터 번들이 없어 mock 번들을 서빙합니다({MOCK_DIR}). meta.is_mock=true", file=sys.stderr)
        root = MOCK_DIR
    return BundleStore(root), str(root)


def create_app(bundle_dir: Path | None = None) -> FastAPI:
    """API 서버 객체를 만든다. 테스트에서는 bundle_dir로 mock 번들을 지정해 쓴다."""
    load_env()
    store, root = _make_store(bundle_dir)
    app = FastAPI(title="공공와이파이 안전 지도 API", version="1.0.0",
                  description=f"※ {DISCLAIMER}  정적 번들(contracts/ 스키마)과 같은 JSON을 서빙합니다.")
    app.state.store = store   # 각 주소 처리 함수가 request.app.state.store로 창고를 꺼내 쓴다
    # CORS: 다른 주소(예: 화면 사이트)에서 이 API를 불러도 되는지 허락하는 목록. 환경변수 CORS_ORIGINS에 쉼표로 적는다.
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT"], allow_headers=["*"],
                       expose_headers=["X-Disclaimer"])

    # 미들웨어: 모든 요청·응답이 지나가는 중간 단계. 여기서는 모든 응답에 X-Disclaimer 머리말을 붙인다.
    @app.middleware("http")
    async def disclaimer_header(request, call_next):
        response = await call_next(request)
        response.headers["X-Disclaimer"] = DISCLAIMER_HEADER
        return response

    # 첫 주소("/")로 접속하면 안내 문구와 API 문서 위치를 알려 준다.
    @app.get("/")
    def root_info():
        return {"disclaimer": DISCLAIMER, "docs": "/docs", "bundle": str(root)}

    # 주소별 처리 묶음(router)을 서버에 연결한다.
    app.include_router(bundle_routes.router)   # 번들 문서(지점·지역·상세 등)
    app.include_router(explain.router)         # 지점 자동 설명
    app.include_router(user_routes.router)     # 로그인·회원·검색·내 위치
    return app


app = create_app()
