"""GPS 최근접 지역(#18)과 구글·네이버 로그인·회원 지역(#19).

[이 파일이 하는 일]
  - /api/nearest   : 내 위치(위도·경도)에서 가장 가까운 지역 찾기
  - /api/search    : 장소 이름·주소 검색
  - /api/auth/...  : 구글·네이버 로그인 (로그인하면 출입증 토큰을 준다)
  - /api/me        : 내 회원 정보 보기, 사는 지역 바꾸기

[로그인 흐름]
  ① 화면에서 구글/네이버 로그인 창을 띄우면, 그 회사가 화면에 '로그인 증표'를 준다.
  ② 화면이 그 증표를 이 서버로 보낸다.
  ③ 서버가 구글/네이버에 "이 증표 진짜 맞나요?"라고 직접 물어 확인한다(화면을 그대로 믿지 않음).
  ④ 진짜면 회원 정보를 DB에 저장하고, 우리 서버의 출입증(session.py 토큰)을 발급한다.

- 토큰 검증은 서버에서 한다: 구글 ID 토큰은 tokeninfo(aud=GOOGLE_CLIENT_ID), 네이버는 /v1/nid/me.
- 회원 정보는 Neon users 테이블(제공자·제공자 ID·표시이름·사는 지역만). DB가 없으면 503.
- 개발용 로그인은 DEV_LOGIN=1 일 때만(로컬). 배포 환경에는 설정하지 않는다.
※ 주소 처리 함수에 새 docstring을 넣으면 /docs 설명서가 바뀌므로 추가 설명은 # 주석으로 단다.
"""
from __future__ import annotations

import math
import os

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request

from api import models as M
from api import session

router = APIRouter(prefix="/api")
# 구글·네이버에 로그인 증표를 확인하는 주소
GOOGLE_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
NAVER_ME = "https://openapi.naver.com/v1/nid/me"


def _store(request: Request):
    # main.py에서 넣어 둔 창고를 꺼낸다
    return request.app.state.store


def _db(request: Request):
    # 회원 기능에 필요한 DB 연결을 준비한다. DB나 비밀값이 없으면 503(지금은 쓸 수 없음)으로 답한다.
    # hasattr(store, "conn"): 창고가 DbStore(DB 연결 있음)인지 확인하는 방법
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
# GET /api/nearest?lat=37.5&lng=127.0 — 위도는 33~39.5, 경도는 124~132(한국 범위)만 받는다
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
        # 위도·경도 차이를 미터로 바꿔(1도 ≈ 111km) 피타고라스 공식으로 거리를 구한다
        dy = (r["center"]["lat"] - lat) * 111_000
        dx = (r["center"]["lng"] - lng) * 111_000 * math.cos(math.radians(lat))
        return math.hypot(dx, dy)
    best = min(regions, key=dist)
    return {"region_id": best["region_id"], "distance_m": None, "method": "region_center"}


# ── 장소 검색 ─────────────────────────────────────────────────
# GET /api/search?q=화정역&region_id=41-goyang&limit=20
@router.get("/search", response_model=M.SearchResponse)
def search(request: Request, q: str = Query(min_length=1, max_length=100),
           region_id: str | None = None, limit: int = Query(default=20, ge=1, le=50)):
    """장소명·주소·설치장소상세에서 찾는다(전국). DB가 없으면 번들에 든 지역의 장소명만."""
    q = q.strip()
    store = _store(request)
    if hasattr(store, "conn"):
        from wifisafe import db
        return {"query": q, "method": "db", "hits": db.search_points(store.conn(), q, region_id, limit)}
    # DB가 없을 때: 번들 지점 이름 + 시도·시군구 이름에 검색어 단어가 모두 들어 있는 지점을 찾는다
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
    # 정렬: 지금 보는 지역 먼저 → 이름에 첫 단어가 든 것 먼저 → 이름순 (False가 True보다 앞에 온다)
    hits.sort(key=lambda h: (h["region_id"] != region_id, toks[0] not in h["name"].lower(), h["name"], h["key"]))
    return {"query": q, "method": "names", "hits": hits[:limit]}


# ── 로그인 ────────────────────────────────────────────────────
def _login(request: Request, provider: str, provider_id: str, name: str) -> dict:
    # 확인이 끝난 사용자를 DB에 저장하고 출입증을 발급한다. 사는 지역이 아직 없으면 needs_region=True
    db, conn = _db(request)
    user = db.upsert_user(conn, provider, provider_id, name or f"{provider} 사용자")
    return {"token": session.issue(user["id"]), "user": user, "needs_region": not user["sido"]}


# POST /api/auth/google — 구글 ID 토큰 확인
# aud(이 토큰이 누구에게 발급됐는지)가 우리 앱 ID와 같고, iss(발급자)가 구글이어야 통과
@router.post("/auth/google", response_model=M.AuthResponse)
def auth_google(body: M.GoogleLogin, request: Request):
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(503, "GOOGLE_CLIENT_ID가 설정되지 않았습니다")
    r = httpx.get(GOOGLE_TOKENINFO, params={"id_token": body.credential}, timeout=10)
    info = r.json() if r.status_code == 200 else {}
    if info.get("aud") != client_id or info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "구글 로그인 정보를 확인하지 못했습니다")
    return _login(request, "google", info["sub"], info.get("name", ""))   # sub = 구글 사용자 고유번호


# POST /api/auth/naver — 네이버 접근 토큰으로 내 정보 조회가 되면 통과 (resultcode "00" = 성공)
@router.post("/auth/naver", response_model=M.AuthResponse)
def auth_naver(body: M.NaverLogin, request: Request):
    r = httpx.get(NAVER_ME, headers={"Authorization": f"Bearer {body.access_token}"}, timeout=10)
    data = r.json() if r.status_code == 200 else {}
    prof = data.get("response") or {}
    if data.get("resultcode") != "00" or not prof.get("id"):
        raise HTTPException(401, "네이버 로그인 정보를 확인하지 못했습니다")
    return _login(request, "naver", prof["id"], prof.get("name") or prof.get("nickname") or "")


# POST /api/auth/dev — 개발용 가짜 로그인. DEV_LOGIN=1이 아니면 주소가 없는 것처럼(404) 숨긴다
@router.post("/auth/dev", response_model=M.AuthResponse)
def auth_dev(request: Request):
    if os.environ.get("DEV_LOGIN") != "1":
        raise HTTPException(404, "Not Found")
    return _login(request, "dev", "local-dev", "개발자")


# ── 내 정보 ───────────────────────────────────────────────────
def _me(request: Request, authorization: str | None):
    # 요청 머리말의 "Authorization: Bearer <토큰>"을 확인해 로그인한 회원을 찾는다. 없으면 401(로그인 필요)
    db, conn = _db(request)
    token = (authorization or "").removeprefix("Bearer ").strip()
    uid = session.verify(token) if token else None
    user = db.get_user(conn, uid) if uid else None
    if not user:
        raise HTTPException(401, "로그인이 필요합니다")
    return db, conn, user


# GET /api/me — 내 회원 정보
@router.get("/me", response_model=M.User)
def me(request: Request, authorization: str | None = Header(default=None)):
    return _me(request, authorization)[2]


# PUT /api/me/region — 사는 지역 바꾸기. 시군구(region_id)까지 고르거나, 시도(sido_code)만 고를 수 있다
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
