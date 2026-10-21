"""contracts/mock/ 가짜 번들 + mock 기반 golden_scores.json 생성 (plan.md §6.5).

[이 파일이 하는 일]
  실제 데이터가 없어도 화면 개발과 테스트를 할 수 있도록, 가상의 지점 40곳으로 '가짜 번들'을 만듭니다.
  가짜 지역 이름은 "샘플시 가상구"(region_id "99-gasang")이고, 이름에 [샘플]·(가상)을 붙여 실제와 헷갈리지 않게 합니다.
  두 날짜의 가짜 스냅샷을 만들어(3곳 삭제, 3곳 추가) 추가·삭제 기능도 확인할 수 있게 합니다.
  테스트(test_api.py 등)와 화면의 ?data=mock 모드가 이 번들을 씁니다.

실제 파이프라인(clean_frame → score_frame → write_bundle)을 가상의 원본 행에 그대로 통과시킨다.
※ mock 값은 발표 화면에 절대 쓰지 않는다. meta.is_mock=true.

실행: python pipeline/make_mock.py [--no-golden]
"""
import argparse
import random
import shutil

import _bootstrap  # noqa: F401
import pandas as pd

from wifisafe import bundle as B
from wifisafe.changes import diff_snapshots
from wifisafe.engine import clean_frame, r1_region_status, score_frame
from wifisafe.io import GOLDEN_PATH, MOCK_DIR, validate_bundle, write_json
from wifisafe.rules import RuleTables
from wifisafe.schema import COLUMN_MAP, ID_COLUMN

N_POINTS = 40                                  # 가짜 지점 수
SNAP_1, SNAP_2 = "2026-10-13", "2026-10-20"    # 가짜 스냅샷 두 날짜
CENTER = (37.5000, 126.9500)   # 가상 지역 표시용 좌표(실제 지점 아님)

# 가짜 데이터용 분류표 (실제 config/ 파일 대신 사용)
MOCK_TABLES = RuleTables(
    ssid_labels={"MOCK_Free_WiFi": "open", "MOCK_Public_Open": "open", "MOCK_Secure": "secure",
                 "MOCK_Unknown": "unknown"},
    facility_map={"교통시설(가상)": (1.0, "가상 규칙: 유동인구 많음"), "공원(가상)": (0.75, "가상 규칙: 실외 공공장소"),
                  "시장(가상)": (0.75, "가상 규칙: 상권"), "공공청사(가상)": (0.25, "가상 규칙: 관리 인력 상주"),
                  "도서관(가상)": (0.25, "가상 규칙: 실내 공공시설")},
    outdoor_keywords=("정류장", "공원", "광장", "거리", "시장"),
)
FACILITIES = [("교통시설(가상)", "샘플 버스정류장"), ("공원(가상)", "샘플 근린공원"), ("시장(가상)", "샘플 전통시장 거리"),
              ("공공청사(가상)", "샘플 주민센터 1층 로비"), ("도서관(가상)", "샘플 도서관 열람실"), ("미분류(가상)", "샘플 기타시설")]
SSIDS = ["MOCK_Free_WiFi", "MOCK_Free_WiFi", "MOCK_Public_Open", "MOCK_Secure", "MOCK_Unknown", "MOCK_Unlabeled"]


def fake_rows(n: int, seed: int, start: int = 0) -> pd.DataFrame:
    """원본 CSV와 같은 칸 이름을 가진 가짜 행 n개를 만든다.

    seed(무작위 시작값)를 고정해서 매번 똑같은 가짜 데이터가 나온다. start는 관리번호를 몇 번부터 붙일지.
    빈칸·잘못된 전화번호('000') 같은 문제 값도 일부러 섞어 각 위험요인이 골고루 나오게 한다.
    """
    rng = random.Random(seed)
    rows = []
    for i in range(start, start + n):
        fac, detail = FACILITIES[i % len(FACILITIES)]
        cluster = i % 4   # 일부 지점을 모아 R5 밀집도가 생기게 함
        lat = CENTER[0] + cluster * 0.004 + rng.uniform(-0.0006, 0.0006)
        lng = CENTER[1] + cluster * 0.005 + rng.uniform(-0.0008, 0.0008)
        year = rng.choice([2013, 2015, 2017, 2019, 2021, 2023, 2025, None])
        rows.append({
            "관리번호": f"MOCK{i + 1:06d}",
            "설치장소명": f"[샘플] 가상지점 {i + 1:02d}",
            "설치장소상세": detail,
            "설치시도명": "샘플시",
            "설치시군구명": "가상구",
            "설치시설구분명": fac,
            "서비스제공사명": rng.choice(["가상통신", "가상통신", "", "기타"]),
            "와이파이SSID": SSIDS[i % len(SSIDS)],
            "설치연월": f"{year}-{rng.randint(1, 12):02d}" if year else "",
            "소재지도로명주소": f"샘플시 가상구 예시로 {i + 1}",
            "소재지지번주소": "",
            "관리기관명": rng.choice(["가상구청", "가상구청", ""]),
            "관리기관전화번호": rng.choice(["02-000-0000", "02-000-0000", "", "000"]),
            "WGS84위도": f"{lat:.6f}",
            "WGS84경도": f"{lng:.6f}",
            "데이터기준일자": rng.choice(["2026-10-18", "2026-03-02", "2025-06-30", ""]),
        })
    df = pd.DataFrame(rows)
    assert set(COLUMN_MAP) | {ID_COLUMN} == set(df.columns), "mock 컬럼이 COLUMN_MAP과 어긋남"
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-golden", action="store_true", help="contracts/golden_scores.json을 덮어쓰지 않음")
    args = ap.parse_args()

    # 실제 파이프라인과 같은 순서: 정제 → 채점 → 스냅샷 비교
    raw1 = fake_rows(N_POINTS, seed=1)
    raw2 = pd.concat([raw1.iloc[3:], fake_rows(3, seed=2, start=N_POINTS)], ignore_index=True)   # 3개 삭제, 3개 추가
    c1, _ = clean_frame(raw1, mock=True)
    c2, rep = clean_frame(raw2, mock=True)
    scored = score_frame(c2, MOCK_TABLES, pd.Timestamp(SNAP_2))
    rid = scored["region_id"].iloc[0]
    changes = diff_snapshots(c1, c2, SNAP_1, SNAP_2)

    if MOCK_DIR.exists():
        shutil.rmtree(MOCK_DIR)
    meta = B.meta_json(is_mock=True, r1_confirmed=False, app_mode="mock", data_reference_date="2026-10-18",
                       snapshot_collected_at=SNAP_2, snapshot_count=2, regions_in_bundle=[rid],
                       sources=[{"id": "MOCK", "name": "가상 데이터(발표 사용 금지)", "dataset_id": None,
                                 "url": "contracts/mock", "retrieved_at": None}])
    background = {"included_in_score": False, "notice": "이 통계는 지점 점수에 반영하지 않습니다", "datasets": [{
        "id": "mock-series", "title": "[샘플] 가상 통계 — 화면 배치 확인용", "unit": "건",
        "note": "가상 값입니다. 발표에 쓰지 마세요.",
        "source": {"name": "가상 데이터", "dataset_id": None, "url": "contracts/mock", "published_at": None,
                   "retrieved_at": SNAP_2},
        "series": [{"label": f"가상 {y}", "value": v, "group": None} for y, v in ((1, 10), (2, 14), (3, 9))],
    }]}
    cases = {"label": "같은 원리 사례 — 국내 공공와이파이 사건 아님", "cases": [{
        "id": "mock-case", "title": "[샘플] 가상 사례 카드", "summary": "화면 배치 확인용 가상 사례입니다.",
        "principle": "가짜 AP(이블 트윈) 원리 설명 자리", "related_rules": ["R1", "R5"],
        "source": {"name": "가상 출처", "dataset_id": None, "url": "contracts/mock", "published_at": SNAP_1,
                   "retrieved_at": SNAP_2},
    }]}
    # mock은 사람이 확정한 라벨이 없으므로 확정 SSID 없음 → 모든 지역 provisional
    regions = B.regions_json(c2, {rid}, rid, r1_region_status(c2, set()))
    B.write_bundle(MOCK_DIR, meta=meta, regions=regions, scored=scored, region_ids=[rid], changes=changes,
                   snapshots=[SNAP_1, SNAP_2], background=background, cases=cases)
    errors = validate_bundle(MOCK_DIR)
    if errors:
        raise SystemExit("mock 번들 스키마 검증 실패:\n  " + "\n  ".join(errors[:30]))
    print(f"mock 번들 생성: {MOCK_DIR}  region={rid}  points={len(scored)}  changes={len(changes)}  스키마 검증 통과")
    print("  등급 분포:", scored["grade"].value_counts().to_dict())

    if not args.no_golden:
        sample = scored[[f"r{i}" for i in range(1, 9)]].head(15).to_numpy().tolist()
        golden = B.golden_json(sample, "mock")
        write_json(GOLDEN_PATH, golden)
        print(f"golden 생성: {GOLDEN_PATH}  cases={len(golden['cases'])}")


if __name__ == "__main__":
    main()
