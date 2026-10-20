"""번들 그대로 서빙하는 GET 엔드포인트 (plan.md §6.1 표와 1:1)."""
from fastapi import APIRouter, HTTPException, Request

from api import models as M

router = APIRouter(prefix="/api")


def _store(request: Request):
    return request.app.state.store


def _region(request: Request, folder: str, region_id: str):
    data = _store(request).region_file(folder, region_id)
    if data is None:
        raise HTTPException(404, f"번들에 없는 지역: {region_id}")
    return data


@router.get("/meta", response_model=M.Meta)
def meta(request: Request):
    return _store(request).get("meta.json")


@router.get("/rules", response_model=M.Rules)
def rules(request: Request):
    return _store(request).get("rules.json")


@router.get("/regions", response_model=M.Regions)
def regions(request: Request):
    return _store(request).get("regions.json")


@router.get("/regions/{region_id}/points", response_model=M.Points)
def points(region_id: str, request: Request):
    return _region(request, "points", region_id)


@router.get("/regions/{region_id}/changes", response_model=M.Changes)
def changes(region_id: str, request: Request):
    return _region(request, "changes", region_id)


@router.get("/regions/{region_id}/sensitivity", response_model=M.Sensitivity)
def sensitivity(region_id: str, request: Request):
    return _region(request, "sensitivity", region_id)


@router.get("/points/{key}", response_model=M.Detail)
def point_detail(key: str, request: Request):
    d = _store(request).detail(key)
    if d is None:
        raise HTTPException(404, f"없는 지점 key: {key}")
    return d


@router.get("/background", response_model=M.Background)
def background(request: Request):
    return _store(request).get("background.json")


@router.get("/cases", response_model=M.Cases)
def cases(request: Request):
    return _store(request).get("cases.json")
