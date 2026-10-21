"""번들 그대로 서빙하는 GET 엔드포인트 (plan.md §6.1 표와 1:1).

[이 파일이 하는 일]
  화면이 "이 주소로 데이터 주세요"라고 요청(GET)하면, 창고(store.py)에서 번들 문서를 꺼내 그대로 돌려줍니다.
  (엔드포인트: 요청을 받는 주소 하나하나. 예) /api/rules)
  `response_model=M.xxx`는 돌려줄 데이터가 models.py에 정한 모양과 맞는지 검사하라는 뜻입니다.
  주소 안의 {region_id}, {key}는 바뀌는 부분입니다. 예) /api/regions/41-goyang/points
※ 각 함수에 설명 문자열(docstring)을 넣으면 /docs API 설명서가 바뀌므로 # 주석으로만 설명한다.
"""
from fastapi import APIRouter, HTTPException, Request

from api import models as M

# 이 파일의 모든 주소 앞에 /api가 붙는다
router = APIRouter(prefix="/api")


def _store(request: Request):
    # main.py에서 넣어 둔 창고(BundleStore 또는 DbStore)를 꺼낸다
    return request.app.state.store


def _region(request: Request, folder: str, region_id: str):
    # 지역별 파일을 꺼낸다. 없으면 404(찾을 수 없음) 오류로 답한다
    data = _store(request).region_file(folder, region_id)
    if data is None:
        raise HTTPException(404, f"번들에 없는 지역: {region_id}")
    return data


# GET /api/meta — 번들 전체 정보
@router.get("/meta", response_model=M.Meta)
def meta(request: Request):
    return _store(request).get("meta.json")


# GET /api/rules — 위험요인 설명·등급표·채점 숫자
@router.get("/rules", response_model=M.Rules)
def rules(request: Request):
    return _store(request).get("rules.json")


# GET /api/regions — 시도·시군구 목록
@router.get("/regions", response_model=M.Regions)
def regions(request: Request):
    return _store(request).get("regions.json")


# GET /api/regions/{region_id}/points — 한 지역의 지도 지점 목록
@router.get("/regions/{region_id}/points", response_model=M.Points)
def points(region_id: str, request: Request):
    return _region(request, "points", region_id)


# GET /api/regions/{region_id}/changes — 한 지역의 최근 추가·삭제 지점
@router.get("/regions/{region_id}/changes", response_model=M.Changes)
def changes(region_id: str, request: Request):
    return _region(request, "changes", region_id)


# GET /api/regions/{region_id}/sensitivity — 한 지역의 민감도 분석 결과
@router.get("/regions/{region_id}/sensitivity", response_model=M.Sensitivity)
def sensitivity(region_id: str, request: Request):
    return _region(request, "sensitivity", region_id)


# GET /api/points/{key} — 지점 하나의 상세 정보 (지점을 눌렀을 때)
@router.get("/points/{key}", response_model=M.Detail)
def point_detail(key: str, request: Request):
    d = _store(request).detail(key)
    if d is None:
        raise HTTPException(404, f"없는 지점 key: {key}")
    return d


# GET /api/background — 배경 통계 (점수 미반영)
@router.get("/background", response_model=M.Background)
def background(request: Request):
    return _store(request).get("background.json")


# GET /api/cases — 같은 원리 사례 카드
@router.get("/cases", response_model=M.Cases)
def cases(request: Request):
    return _store(request).get("cases.json")
