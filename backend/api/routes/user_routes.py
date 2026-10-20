"""GPS 최근접 지역(#18)과 구글·네이버 로그인·회원 지역(#19).

- 토큰 검증은 서버에서 한다: 구글 ID 토큰은 tokeninfo(aud=GOOGLE_CLIENT_ID), 네이버는 /v1/nid/me.
- 회원 정보는 Neon users 테이블(제공자·제공자 ID·표시이름·사는 지역만). DB가 없으면 503.
- 개발용 로그인은 DEV_LOGIN=1 일 때만(로컬). 배포 환경에는 설정하지 않는다.
"""
from __future__ import annotations

import math
import os

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request

from api import models as M
from api import session

router = APIRouter(prefix="/api")
GOOGLE_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
NAVER_ME = "https://openapi.naver.com/v1/nid/me"


def _store(request: Request):
    return request.app.state.store


def _db(request: Request):
    store = _store(request)
    if not hasattr(store, "conn"):
        raise HTTPException(503, "회원 기능은 DB(DATABASE_URL)가 있을 때만 쓸 수 있습니다")
    try:
        session._secret()
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    from wifisafe import db
    return db, store.conn()


# ── GPS ───────────────────────────────────────────────────────
@router.get("/nearest", response_model=M.NearestResponse)
def nearest(request: Request, lat: float = Query(ge=33.0, le=39.5), lng: float = Query(ge=124.0, le=132.0)):
    """좌표 → 가장 가까운 와이파이 지점의 지역. DB가 없으면 regions.json의 지역 중심점 중 가장 가까운 곳."""
    store = _store(request)
    if hasattr(store, "conn"):
        from wifisafe import db
        hit = db.nearest_region(store.conn(), lat, lng)
        if hit:
            return {**hit, "method": "postgis"}
    regions = [r for r in store.get("regions.json")["regions"] if r["available"]]
    if not regions:
        raise HTTPException(404, "데이터가 있는 지역이 없습니다")

    def dist(r):   # 근거리라 평면 근사로 충분
        dy = (r["center"]["lat"] - lat) * 111_000
        dx = (r["center"]["lng"] - lng) * 111_000 * math.cos(math.radians(lat))
        return math.hypot(dx, dy)
    best = min(regions, key=dist)
    return {"region_id": best["region_id"], "distance_m": None, "method": "region_center"}


# ── 장소 검색 ─────────────────────────────────────────────────
@router.get("/search", response_model=M.SearchResponse)
def search(request: Request, q: str = Query(min_length=1, max_length=100),
           region_id: str | None = None, limit: int = Query(default=20, ge=1, le=50)):
    """장소명·주소·설치장소상세에서 찾는다(전국). DB가 없으면 번들에 든 지역의 장소명만."""
    q = q.strip()
    store = _store(request)
    if hasattr(store, "conn"):
        from wifisafe import db
        return {"query": q, "method": "db", "hits": db.search_points(store.conn(), q, region_id, limit)}
    toks = [t.lower() for t in q.split()]
    hits = []
    for r in store.get("regions.json")["regions"]:
        if not r["available"]:
            continue
        for p in store.region_file("points", r["region_id"])["points"]:
            text = f"{p['name']} {r['sido']} {r['sigungu']}".lower()
            if all(t in text for t in toks):
                hits.append({"key": p["key"], "region_id": r["region_id"], "sido": r["sido"], "sigungu": r["sigungu"],
                             "name": p["name"], "address": None, "place_detail": None, "lat": p["lat"], "lng": p["lng"]})
    hits.sort(key=lambda h: (h["region_id"] != region_id, toks[0] not in h["name"].lower(), h["name"], h["key"]))
    return {"query": q, "method": "names", "hits": hits[:limit]}


# ── 로그인 ────────────────────────────────────────────────────
def _login(request: Request, provider: str, provider_id: str, name: str) -> dict:
    db, conn = _db(request)
    user = db.upsert_user(conn, provider, provider_id, name or f"{provider} 사용자")
    return {"token": session.issue(user["id"]), "user": user, "needs_region": not user["sido"]}


@router.post("/auth/google", response_model=M.AuthResponse)
def auth_google(body: M.GoogleLogin, request: Request):
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(503, "GOOGLE_CLIENT_ID가 설정되지 않았습니다")
    r = httpx.get(GOOGLE_TOKENINFO, params={"id_token": body.credential}, timeout=10)
    info = r.json() if r.status_code == 200 else {}
    if info.get("aud") != client_id or info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "구글 로그인 정보를 확인하지 못했습니다")
    return _login(request, "google", info["sub"], info.get("name", ""))


@router.post("/auth/naver", response_model=M.AuthResponse)
def auth_naver(body: M.NaverLogin, request: Request):
    r = httpx.get(NAVER_ME, headers={"Authorization": f"Bearer {body.access_token}"}, timeout=10)
    data = r.json() if r.status_code == 200 else {}
    prof = data.get("response") or {}
    if data.get("resultcode") != "00" or not prof.get("id"):
        raise HTTPException(401, "네이버 로그인 정보를 확인하지 못했습니다")
    return _login(request, "naver", prof["id"], prof.get("name") or prof.get("nickname") or "")


@router.post("/auth/dev", response_model=M.AuthResponse)
def auth_dev(request: Request):
    if os.environ.get("DEV_LOGIN") != "1":
        raise HTTPException(404, "Not Found")
    return _login(request, "dev", "local-dev", "개발자")


# ── 내 정보 ───────────────────────────────────────────────────
def _me(request: Request, authorization: str | None):
    db, conn = _db(request)
    token = (authorization or "").removeprefix("Bearer ").strip()
    uid = session.verify(token) if token else None
    user = db.get_user(conn, uid) if uid else None
    if not user:
        raise HTTPException(401, "로그인이 필요합니다")
    return db, conn, user


@router.get("/me", response_model=M.User)
def me(request: Request, authorization: str | None = Header(default=None)):
    return _me(request, authorization)[2]


@router.put("/me/region", response_model=M.User)
def set_region(body: M.RegionUpdate, request: Request, authorization: str | None = Header(default=None)):
    db, conn, user = _me(request, authorization)
    regions = _store(request).get("regions.json")
    if body.region_id:
        r = next((r for r in regions["regions"] if r["region_id"] == body.region_id), None)
        if r is None:
            raise HTTPException(422, f"없는 지역: {body.region_id}")
        return db.set_user_region(conn, user["id"], r["sido"], r["sigungu"], r["region_id"])
    s = next((s for s in regions["sido"] if s["sido_code"] == body.sido_code), None)
    if s is None:
        raise HTTPException(422, "region_id 또는 올바른 sido_code가 필요합니다")
    return db.set_user_region(conn, user["id"], s["sido"], None, None)
