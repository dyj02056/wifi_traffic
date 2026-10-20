# 담당 B 인계 문서 — Next.js 프론트엔드와 API

> 2026-10-20 작성. 원래 B 몫이던 Next.js 앱(`frontend/`)을 A가 먼저 만들었다. 이 문서는 B가 이어받을 때 읽는 요약이다.
> 결정 근거는 모두 [docs/requests.md](requests.md) 번호로 적었다.

## 0. 배포 (2026-10-21)
| 용도 | 주소 | Vercel 프로젝트 / 루트 폴더 |
|---|---|---|
| 화면 | https://wifi-traffic.vercel.app | `wifi-traffic` / `frontend` (Next.js) |
| API | https://wifi-traffic-api.vercel.app | `wifi-traffic-api` / `backend` (FastAPI 프리셋, `app.py`, 지역 sin1) |

- main에 푸시하면 두 프로젝트가 자동으로 다시 배포된다.
- API 환경변수: `DATABASE_URL` `SESSION_SECRET` `GOOGLE_CLIENT_ID` `CORS_ORIGINS`(=화면 주소,http://localhost:3000). `DEV_LOGIN`은 넣지 않는다.
- 화면 환경변수: `NEXT_PUBLIC_API_BASE`(=API 주소/api) `NEXT_PUBLIC_DATA_BASE=/data` `NEXT_PUBLIC_KAKAO_JS_KEY` `NEXT_PUBLIC_GOOGLE_CLIENT_ID` `NEXT_PUBLIC_NAVER_CLIENT_ID`
- 화면 주소를 카카오(JS SDK 도메인)·구글(승인된 자바스크립트 원본)·네이버(서비스 URL, Callback URL `…/`)에 등록함.
- 매일 수집: GitHub Actions Secret `DATABASE_URL` 필요.

## 1. 바뀐 큰 그림

| 항목 | 계획서(plan.md) | 지금 |
|---|---|---|
| 데이터 원본 | 사람이 D1 CSV를 2~3일마다 다운로드 | **GitHub Actions가 매일 KST 05:00 LOCALDATA 전국 파일 자동 수집** (#15·#17) |
| 저장 | 정적 번들 파일 | **Neon(Postgres+PostGIS)** `bundle_docs`에 같은 JSON 저장, API가 읽음 (#15) |
| API | FastAPI 로컬 | **Vercel FastAPI 프리셋**(`backend/app.py` 진입점, `backend/vercel.json` 지역 sin1, #41), DB 없으면 파일 번들 (#17) |
| 화면 데이터 | `NEXT_PUBLIC_DATA_BASE` 하나 | API 우선 → 응답 없으면 정적 번들(`public/data`)로 자동 전환 + "정적 백업 데이터" 배지 (#16) |
| 지도 | MapLibre + OpenFreeMap | **카카오맵** (#31) |
| 로그인 | 없음 | **구글·네이버(서버 검증) + 비회원**, 로컬 전용 개발용 로그인, 아이디·비밀번호 없음 (#19) |
| 첫 지역 | `default_region_id` | `?region` → 회원 가입 지역 → **"내 위치" 버튼(GPS, 누를 때만)** → 기본 지역 고양시 (#18·#34) |
| "임시(무효)" | `meta.r1_confirmed` 하나 | **지역별** `regions[].r1_status` (#23·#24) |

## 2. 계약 1.0.0 → 1.1.0 (`contracts/`)
- `regions.json`의 각 지역에 `r1_status`(`confirmed` / `provisional` / `no_ssid`)와 `r1_coverage`(SSID 있는 행 중 확정 라벨 비율, no_ssid면 null) 추가
- 화면 규칙: `provisional` → "임시(무효) — SSID 라벨 미확정" 배지 + 지도 워터마크, `no_ssid` → "SSID 정보 없음 — 보안접속 항목(R1)은 가정값" 배지만, `confirmed` → 없음
- `meta.r1_confirmed`는 "번들의 모든 지역이 provisional이 아님"이라는 요약값(호환용)
- `rules.params.R1_REGION_COVERAGE_MIN = 0.9` 추가
- 반올림은 `floor(x*100+0.5+1e-9)/100` (#5) — `src/lib/score.ts`, golden 51건 통과
- `regions[].bbox`는 위·경도 바깥 2%를 뺀 범위, 동떨어진 좌표 지점에는 flag `COORD_suspect`(표시만, 점수 영향 없음) (#32)
- API `GET /api/search?q=&region_id=` — 전국 장소명·주소 검색(DB), 화면은 카카오 주소·장소 검색과 함께 보여 줌 (#33)

## 3. API 경로 (`backend/api/`)
기존 번들 경로(`/api/meta` `/rules` `/regions` `/regions/{id}/points|changes|sensitivity` `/points/{key}` `/background` `/cases`, `POST /points/{key}/explain`)는 그대로. 추가:

| 경로 | 설명 |
|---|---|
| `GET /api/nearest?lat=&lng=` | 가장 가까운 지점의 `region_id` (DB: PostGIS, 없으면 지역 중심점) |
| `POST /api/auth/google {credential}` | 구글 ID 토큰 검증(aud=`GOOGLE_CLIENT_ID`) → `{token, user, needs_region}` |
| `POST /api/auth/naver {access_token}` | 네이버 `/v1/nid/me`로 확인 |
| `POST /api/auth/dev` | `DEV_LOGIN=1`일 때만(로컬) |
| `GET /api/me`, `PUT /api/me/region {region_id \| sido_code}` | `Authorization: Bearer <token>` (HMAC 서명, `SESSION_SECRET`) |

회원 테이블은 provider·provider_id·표시이름·시도·시군구·region_id만 저장한다(이메일 저장 안 함).

## 4. frontend 구조
`src/app/{page,map,rules,sensitivity,context,about}`, `src/components/`(KakaoMap, WeightPanel, RankTable, PointSheet, Summary, LoginCard, DocShell…), `src/lib/`(api·auth·score·queries·types), `src/store/useAppStore.ts`. 실행법은 [frontend/README.md](../frontend/README.md).
- 스타일은 web-draft CSS를 옮겨 와 `globals.css`에 두었다(Tailwind는 설치만, 필요하면 점진 전환).
- Next.js 16(Cache Components 켜짐): URL을 읽는 화면은 `Suspense` 안에서 렌더링, 외부 상태는 `useSyncExternalStore`.

## 5. 아직 남은 일 (B가 이어서)
- [x] 카카오 JavaScript 키 발급·도메인 등록(로컬 3000, Vercel 주소), 지도 동작 확인
- [x] 마커가 많은 지역(강남구 2,807개) 성능 확인 — 문제 없음, 묶어 보이기는 색이 가려져 넣지 않음(#43)
- [x] 구글·네이버 실제 로그인 확인(로컬, #39). 배포 주소 로그인은 사용자 확인 대기
- [x] Vercel 배포 2개와 환경변수, CORS (위 0절)
- [ ] 계획서 §9.2 효과 중 미구현: 지역 이동 시 마커가 커지며 등장, 선택 마커 펄스, AI 설명 문장 단위 페이드
- [ ] (선택) Playwright 시연 시나리오 E2E
