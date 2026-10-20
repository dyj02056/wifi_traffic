"""FastAPI — backend/dist/data 번들을 그대로 서빙 + /explain (plan.md §8.7).

실행(backend/에서): uvicorn api.main:app --reload --port 8000   → http://localhost:8000/docs
BUNDLE_DIR 환경변수로 다른 번들(예: ../contracts/mock)을 서빙할 수 있다.
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

from api.routes import bundle_routes, explain  # noqa: E402
from api.store import BundleStore  # noqa: E402
from config.rules import DISCLAIMER  # noqa: E402
from wifisafe.io import DIST_DATA_DIR, MOCK_DIR, load_env  # noqa: E402

DISCLAIMER_HEADER = urllib.parse.quote(DISCLAIMER)


def create_app(bundle_dir: Path | None = None) -> FastAPI:
    load_env()
    root = Path(bundle_dir or os.environ.get("BUNDLE_DIR") or DIST_DATA_DIR)
    if not root.is_absolute():
        root = (BACKEND / root).resolve()
    if not (root / "meta.json").exists() and bundle_dir is None and not os.environ.get("BUNDLE_DIR"):
        print(f"⚠ 실데이터 번들이 없어 mock 번들을 서빙합니다({MOCK_DIR}). meta.is_mock=true", file=sys.stderr)
        root = MOCK_DIR
    app = FastAPI(title="공공와이파이 안전 지도 API", version="1.0.0",
                  description=f"※ {DISCLAIMER}  정적 번들(contracts/ 스키마)과 같은 JSON을 서빙합니다.")
    app.state.store = BundleStore(root)
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"],
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
    return app


app = create_app()
