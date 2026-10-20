# 공공와이파이 안전 지도 (Wifi Traffic)

> **※ 이 지도의 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.**

전국 공공와이파이 지점마다 위험요인 점수(0~100)를 매겨 지도에 색으로 표시하고, 가중치 슬라이더로 채점 기준을 직접 바꿔 볼 수 있는 웹사이트. 설계 문서는 [plan.md](plan.md).

| 배포 | 주소 |
|---|---|
| 화면 | https://wifi-traffic.vercel.app |
| API | https://wifi-traffic-api.vercel.app (API 목록 `/docs`) |

시연 순서와 백업 전환은 [docs/demo_script.md](docs/demo_script.md).

| 폴더 | 담당 | 내용 |
|---|---|---|
| [contracts/](contracts/README.md) | A | API 계약: JSON Schema 10종, mock 번들, 골든 테스트 |
| [backend/](backend/) | A | 수집·정제·채점 파이프라인, 매일 수집(Neon), FastAPI(Vercel), 정적 번들 생성 |
| [web-draft/](web-draft/) | A | HTML/CSS/JS 정적 초안 (시안·백업 데모) |
| [frontend/](frontend/README.md) | B(인계: [docs/handoff_B.md](docs/handoff_B.md)) | Next.js 앱 (카카오맵) |
| [scripts/](scripts/) | A | 번들 동기화, 면책 문구 검사 |
| [.github/workflows/](.github/workflows/daily-sync.yml) | A | 매일 KST 05:00 자동 수집 → Neon |
| [docs/](docs/) | | 진행 기록, 승인 요청, 발표·시연 문서 |

## 실행 방법

### 운영 구조 (docs/requests.md #15~#19)
```
GitHub Actions(매일 05:00) → LOCALDATA 전국 CSV → 정제·채점 → Neon(Postgres+PostGIS)
Next.js(frontend, Vercel) → 우리 API(Vercel FastAPI·sin1, Neon 읽기) — 응답 없으면 정적 번들(public/data)로 자동 전환
```

```bash
# ── 백엔드 ──
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-pipeline.txt            # 수집·채점·테스트 (API만이면 requirements.txt)
cp .env.example .env                                # DATABASE_URL(Neon), SESSION_SECRET, DEV_LOGIN=1(로컬) 등

# Neon(DB) 경로 — 매일 수집과 같은 처리
python pipeline/db_migrate.py                        # 스키마·PostGIS (여러 번 실행해도 안전)
python pipeline/daily_sync.py                        # 원본 다운로드 → 정제·채점 → 전 지역 문서를 DB에 (약 5분)
python pipeline/export_bundle_from_db.py --regions 41-goyang,11-seocho,11-guro --default 41-goyang   # 시연 직전 정적 백업 번들 → bash scripts/sync_bundle.sh

# 파일 경로 — DB 없이 로컬 확인용(기존 방식)
python pipeline/ingest_snapshot.py ~/Downloads/무료와이파이정보.csv
python pipeline/census.py && python pipeline/clean.py
python pipeline/score.py --region 11-seocho,11-guro
python pipeline/changes.py && python pipeline/sensitivity.py --region 11-seocho,11-guro
python pipeline/pregen_explanations.py --region 11-seocho,11-guro --template-only
python pipeline/export_bundle.py --regions 11-seocho,11-guro --default 11-seocho

uvicorn api.main:app --reload --port 8000           # API: DATABASE_URL 있으면 Neon, 없으면 dist/data(없으면 mock)
cd .. && bash scripts/sync_bundle.sh                # dist/data → web-draft/data, frontend/public/data

# ── Next.js (frontend/README.md) ──
cd frontend && npm install && cp .env.local.example .env.local && npm run dev   # http://localhost:3000

# ── 정적 초안 (백업 데모) ──
cd web-draft && python -m http.server 5500          # http://localhost:5500  (?data=mock 으로 mock)

# ── 테스트 ──
cd backend && python -m pytest -q                   # DB 테스트까지: TEST_DB=1 python -m pytest -q
cd frontend && npm test                             # golden 51건
node web-draft/tests/score.test.mjs
python scripts/check_disclaimer.py
```

mock 번들 다시 만들기: `python backend/pipeline/make_mock.py` (golden도 mock 기준으로 재생성).

## 데이터 출처

| ID | 데이터 | 용도 |
|---|---|---|
| D1 | 전국무료와이파이표준데이터 ([15013116](https://www.data.go.kr/data/15013116/standard.do)) — 자동 수집은 [LOCALDATA 파일](https://file.localdata.go.kr/file/free_wifi_info/info) | 지점 원장, 채점 입력 |
| D2 | 서울특별시 구로구 공공와이파이 ([15147901](https://www.data.go.kr/data/15147901/fileData.do)) | R1 판정 검증 |
| D3~D5 | 경찰청 사이버범죄 통계, KISA 침해사고 통계 | 배경 패널(**점수 미반영**) |
| D6 | 뉴스 기반 사례 카드 (`backend/data/cases.yaml`) | "같은 원리 사례 — 국내 공공와이파이 사건 아님" |

지도: Next.js는 카카오맵, 정적 초안은 OpenStreetMap(© OpenStreetMap contributors) 또는 카카오맵. 범죄 통계는 점수에 넣지 않는다.
