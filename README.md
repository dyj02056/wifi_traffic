# 공공와이파이 안전 지도 (Wifi Traffic)

> **※ 이 지도의 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.**

전국 공공와이파이 지점마다 위험요인 점수(0~100)를 매겨 지도에 색으로 표시하고, 가중치 슬라이더로 채점 기준을 직접 바꿔 볼 수 있는 웹사이트. 설계 문서는 [plan.md](plan.md).

| 폴더 | 담당 | 내용 |
|---|---|---|
| [contracts/](contracts/README.md) | A | API 계약: JSON Schema 10종, mock 번들, 골든 테스트 |
| [backend/](backend/) | A | 수집·정제·채점 파이프라인, FastAPI, 정적 번들 생성 |
| [web-draft/](web-draft/) | A | HTML/CSS/JS 정적 초안 (시안·백업 데모) |
| frontend/ | B | Next.js 앱 |
| [scripts/](scripts/) | A | 번들 동기화, 면책 문구 검사 |
| [docs/](docs/) | | 진행 기록, 승인 요청, 발표·시연 문서 |

## 실행 방법

```bash
# ── 백엔드 (담당 A) ──
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

python pipeline/ingest_snapshot.py ~/Downloads/전국무료와이파이표준데이터.csv
python pipeline/census.py
#   → config/ssid_labels.csv, facility_map.csv 작성·확정
python pipeline/clean.py
python pipeline/score.py --sido 서울특별시 --sigungu 구로구
python pipeline/changes.py
python pipeline/sensitivity.py --sido 서울특별시 --sigungu 구로구
python pipeline/pregen_explanations.py --region 11-guro         # AI 설명 사전 생성(키 없으면 템플릿)
python pipeline/export_bundle.py --regions 11-guro              # dist/data + contracts/golden 갱신
uvicorn api.main:app --reload --port 8000                       # 선택: API 서버 (/docs)

cd .. && bash scripts/sync_bundle.sh                            # Windows: powershell -File scripts\sync_bundle.ps1

# ── 정적 초안 (담당 A) ──
cd web-draft && python -m http.server 5500                      # http://localhost:5500  (?data=mock 으로 mock)

# ── 테스트 ──
cd backend && python -m pytest -q
node web-draft/tests/score.test.mjs
python scripts/check_disclaimer.py
```

mock 번들 다시 만들기: `python backend/pipeline/make_mock.py` (golden도 mock 기준으로 재생성).

## 데이터 출처

| ID | 데이터 | 용도 |
|---|---|---|
| D1 | 전국무료와이파이표준데이터 ([15013116](https://www.data.go.kr/data/15013116/standard.do)) | 지점 원장, 채점 입력 |
| D2 | 서울특별시 구로구 공공와이파이 ([15147901](https://www.data.go.kr/data/15147901/fileData.do)) | R1 판정 검증 |
| D3~D5 | 경찰청 사이버범죄 통계, KISA 침해사고 통계 | 배경 패널(**점수 미반영**) |
| D6 | 뉴스 기반 사례 카드 (`backend/data/cases.yaml`) | "같은 원리 사례 — 국내 공공와이파이 사건 아님" |

지도 배경 © OpenStreetMap contributors. 범죄 통계는 점수에 넣지 않는다.
