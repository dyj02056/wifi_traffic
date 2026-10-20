"""FastAPI — backend/dist/data 번들을 그대로 서빙 + /explain (plan.md §8.7).

실행(backend/에서): uvicorn api.main:app --reload --port 8000   → http://localhost:8000/docs
DATABASE_URL이 있으면 Neon(bundle_docs)에서, 없으면 파일 번들(dist/data, 없으면 mock)에서 읽는다.
BUNDLE_DIR 환경변수로 다른 파일 번들(예: ../contracts/mock)을 강제할 수 있다.
배포: Vercel 파이썬 함수(backend/vercel.json) — docs/requests.md #17
"""
import os
import sys
import urllib.parse
from pathlib import Path

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

DISCLAIMER_HEADER = urllib.parse.quote(DISCLAIMER)


def _make_store(bundle_dir: Path | None):
    """명시한 파일 번들 > BUNDLE_DIR > DATABASE_URL(Neon) > dist/data > mock 순서."""
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
    load_env()
    store, root = _make_store(bundle_dir)
    app = FastAPI(title="공공와이파이 안전 지도 API", version="1.0.0",
                  description=f"※ {DISCLAIMER}  정적 번들(contracts/ 스키마)과 같은 JSON을 서빙합니다.")
    app.state.store = store
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT"], allow_headers=["*"],
                       expose_headers=["X-Disclaimer"])

    @app.middleware("http")
    async def disclaimer_header(request, call_next):
        response = await call_next(request)
        response.headers["X-Disclaimer"] = DISCLAIMER_HEADER
        return response

    @app.get("/")
    def root_info():
        return {"disclaimer": DISCLAIMER, "docs": "/docs", "bundle": str(root)}

    app.include_router(bundle_routes.router)
    app.include_router(explain.router)
    app.include_router(user_routes.router)
    return app


app = create_app()
