# plan.md — 공공와이파이 안전 지도 (Wifi Traffic) 구현 계획서 v2.1

> 작성일: 2026-10-20 · 팀: 정성 유지 (정성원, 유지은) · 문서 소유: 테크니컬 리드
> v2 변경점: 프론트엔드를 Streamlit → **Next.js**로 전환, **2인 병렬 개발**(백엔드+정적 초안 / Next.js) 구조로 재구성, **API 계약(contract) 우선** 개발 방식 도입
> v2.1 변경점(2026-10-20): ① 예시 점수 계산 오류 수정(74.25 → **75.25**) ② `GET /api/points/{key}`용 **key→region 인덱스**(`data/key_index.json`) 추가, 스키마 9종 → 10종 ③ D1 담당 A 작업을 **오전(계약·mock 선배포) / 오후(수집·census)**로 분리 ④ R5 시군구 경계 한계를 판정표·/about·리스크에 명시
>
> **※ 이 지도의 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.**
> 이 문장은 모든 화면 상단, 지점 상세, README, API 응답 메타데이터, 발표자료 첫 장에 반드시 들어간다.

---

## 0. 이 문서를 받은 LLM(구현 담당)에게 — 공통 작업 규칙

이 규칙은 코드 품질·애니메이션 완성도보다 우선한다. 어기게 되면 **작업을 멈추고 무엇이 막혔는지 보고**한다.

1. **데이터를 지어내지 않는다.** 컬럼명, API 엔드포인트, SSID 값, 통계 수치를 추측해서 코드에 박지 않는다. 모르는 값은 `TODO(확인필요)` + 설정 파일로 뺀다.
2. **R1 게이트를 지킨다.** `backend/config/ssid_labels.csv`가 `status=confirmed`가 아니면 최종 데이터 번들을 만들지 않는다. 개발용 번들에는 `meta.r1_confirmed=false`가 들어가고, 모든 프론트엔드는 이때 "임시(무효)" 워터마크를 띄운다.
3. **가중치는 상수로 분리한다.** 점수 로직에 숫자(30, 20, …)를 직접 쓰지 않는다. 백엔드는 `config/rules.py`, 프론트엔드는 API의 `/rules` 응답에서만 읽는다.
4. **범죄 통계는 점수에 절대 넣지 않는다.** 배경 패널 전용. 점수 모듈은 배경 데이터 모듈을 import하지 않는다.
5. **가정 기반 규칙에는 '가정' 라벨**을 데이터·UI·문서에 붙인다(`is_assumption` 필드로 자동 처리).
6. **외부 수치·사례에는 출처와 날짜**가 없으면 렌더링하지 않는다.
7. **금지 표현:** "해킹 확률", "해킹될 확률", "해킹 위험 지역", "사건 발생 지역", "범죄 다발" 등은 어떤 화면·AI 출력에도 나오면 안 된다(면책 문구 속 부정형만 예외).
8. **목록 밖 데이터 소스를 추가하지 않는다.** 필요하면 `docs/requests.md`에 사유를 쓰고 리드 승인을 기다린다.
9. **계약을 깨지 않는다.** `contracts/`의 스키마를 바꿀 때는 버전을 올리고 상대 담당에게 알린다(§6).
10. 각 마일스톤 끝에 수용 기준을 직접 실행해 확인하고 결과를 `docs/progress.md`에 기록한다.

---

## 1. 제품 정의

| 항목 | 내용 |
|---|---|
| 한 줄 정의 | 전국 공공와이파이 지점마다 위험요인 점수(0~100)를 매겨 지도에 색으로 표시하고, 가중치 슬라이더로 채점 기준을 직접 조작해 볼 수 있는 인터랙티브 웹사이트 |
| 대상 사용자 | 발표 청중(심사위원), 시연용 시민 페르소나(학생·고령층·여행객) |
| 핵심 메시지 | "이 점수는 실제 해킹 확률이 아니라 위험요인 지표다" + "보는 기준에 따라 점수가 달라진다" |
| 하지 않는 것 | 사건 기반 위험 지도, 실시간 AP 스캔, 이용자 위치 수집, 범죄 통계의 점수 반영 |

### 1.1 사용자 흐름 (기획안 작동 단계와 1:1 대응)

1. 시도 → 시군구 선택 → 해당 지역 지점만 로드, 등급 색 마커 지도
2. 지점 클릭 → 상세 패널(총점·등급·R1~R8 항목 점수·근거값·가정 라벨·AI 설명·관리기관 연락처)
3. 위험요인 체크/가중치 슬라이더 조작 → 마커 색이 부드럽게 바뀌고 순위 변동 표가 재정렬
4. 배경 레이어 토글(최근 추가·삭제 지점) + 배경 패널(사이버범죄·침해사고 통계, 점수 미반영)
5. "안전하게 쓰는 법" → 지점 특성별 행동수칙 체크리스트 + 신고 경로

### 1.2 Definition of Done (v2 갱신)

- [ ] `wifi_scored.csv` — 지점별 R1~R8, 위험점수, 등급
- [ ] `wifi_changes.csv` — 스냅샷 비교 추가/삭제 이력 (최소 3~4회 수집분)
- [ ] **백엔드 API + 정적 데이터 번들** — `contracts/` 스키마 준수
- [ ] **정적 초안 웹(HTML/CSS/JS)** — 핵심 흐름 1~3 동작, 시연 백업용
- [ ] **Next.js 웹앱** — 지도 색칠 + R1~R8 가중치 슬라이더 + 배경 레이어 토글 + 동작 효과 (기존 DoD의 "Streamlit 지도 앱"을 대체)
- [ ] 발표자료 — 문제정의 / 데이터 한계 / 채점표 / 민감도 분석 / 데모 시나리오
- [ ] 민감도 분석 1컷 — R1 30→15 시 위험 상위 지점 순위 변화 표

---

## 2. 역할 분담

| | 담당 A — 백엔드 + 정적 초안 | 담당 B — Next.js 프론트엔드 |
|---|---|---|
| 책임 범위 | 데이터 수집·정제·채점 파이프라인, FastAPI, 정적 데이터 번들, **API 계약 소유**, HTML/CSS/JS 초안 홈페이지 | Next.js 앱 전체(화면·상태관리·지도·애니메이션·배포) |
| 산출물 | `backend/`, `contracts/`, `web-draft/`, 3개 CSV, 민감도 분석 | `frontend/`, 배포 URL |
| 핵심 의존 | 실제 CSV, SSID 라벨 확정 | `contracts/`의 스키마와 mock 데이터 |
| 초안의 역할 | 정적 초안은 ① 화면 구성·문구의 1차 시안 ② API 계약이 실제로 쓸 만한지 검증 ③ **시연 당일 Next.js 장애 시 백업 데모** | 초안의 정보 구조·문구를 기준으로 동작 효과와 완성도를 올린다 |

**병렬 개발 원칙:** B는 실제 데이터를 기다리지 않는다. A가 Day 1에 `contracts/mock/`을 먼저 올리고, B는 mock으로 개발하다가 환경변수 하나로 실제 번들/API로 전환한다.

---

## 3. 전체 아키텍처

```
[data.go.kr CSV 스냅샷] ─┐
[구로구 접속환경 CSV] ───┤
[경찰청·KISA API] ───────┤
[cases.yaml(수동)] ──────┘
          │
          ▼
┌──────────────── backend (담당 A, Python) ────────────────┐
│ pipeline/: ingest → census → clean → score → changes      │
│            → sensitivity → validate_guro → export_bundle  │
│ src/wifisafe/: 채점 엔진(순수 함수), 가드레일, AI 설명    │
│ api/: FastAPI — 번들과 같은 JSON을 그대로 서빙 + /explain │
└──────────────────────────┬───────────────────────────────┘
                           │  contracts/ (JSON Schema + mock + golden)
          ┌────────────────┴─────────────────┐
          ▼                                  ▼
 web-draft/ (담당 A)                 frontend/ (담당 B)
 HTML/CSS/JS + Leaflet               Next.js + MapLibre + Motion
 정적 번들 JSON 직접 fetch           번들 또는 API에서 fetch
 → 시안·백업 데모                    → 최종 시연 앱 (Vercel)
```

### 3.1 핵심 설계 결정

1. **재채점은 브라우저에서 한다.** 백엔드는 지점별 위험 비율 `r1..r8`(0~1)만 내려주고, 슬라이더를 움직일 때 총점·등급·순위는 클라이언트에서 계산한다. → 서버 왕복 없이 즉시 반응, 애니메이션이 자연스러움.
2. **공식은 3곳(Python·초안 JS·Next.js TS)에 구현되므로 골든 테스트로 일치를 강제한다.** `contracts/golden_scores.json`(백엔드가 생성)을 세 구현 모두 테스트에서 통과해야 한다(오차 0.01 이하).
3. **정적 번들 우선.** 시연은 정적 JSON 번들로 돌아가야 한다(서버 콜드스타트·네트워크 장애 대비). FastAPI는 개발 편의, AI 실시간 설명, 확장용이다. 시연 지역의 AI 설명은 번들에 미리 생성해 넣는다.
4. **R5(밀집도)는 파이프라인에서 시군구 단위로 사전 계산**(원칙 6). 프론트엔드는 계산하지 않는다.

---

## 4. 기술 스택

### 4.1 백엔드 (담당 A)

| 영역 | 선택 | 이유 |
|---|---|---|
| 언어 | Python 3.11 | 데이터 가공·채점을 한 언어로 |
| 데이터 처리 | pandas, pyarrow | 6.9만 행은 pandas로 충분 |
| 공간 계산 | scikit-learn `BallTree`(haversine) | R5 반경 내 개방형 AP 수 |
| API | FastAPI + uvicorn | 자동 OpenAPI 문서, pydantic 응답 모델로 계약 검증 |
| 검증 | pydantic, PyYAML, jsonschema | 응답·사례 카드 스키마 강제 |
| AI 설명 | Anthropic SDK, 모델 `claude-haiku-5-5` | 근거값만 인용한 2~3문장. 실패 시 템플릿 |
| 테스트 | pytest | 규칙·가드레일·골든 생성 |
| 배포(선택) | Render 또는 Railway | 무료 플랜은 콜드스타트가 있으므로 시연은 정적 번들 사용 |

### 4.2 정적 초안 (담당 A)

| 영역 | 선택 |
|---|---|
| 마크업/스타일 | HTML5, CSS(커스텀 프로퍼티로 등급 색·간격 토큰 정의), 빌드 도구 없음 |
| 스크립트 | 바닐라 JS(ES 모듈), `fetch`로 번들 JSON 로드 |
| 지도 | Leaflet(CDN) + OpenStreetMap 타일(출처 표기 필수) |
| 실행 | `python -m http.server`로 로컬 서빙 (ES 모듈은 file:// 에서 안 됨) |

### 4.3 Next.js 프론트엔드 (담당 B)

| 영역 | 선택 | 이유 |
|---|---|---|
| 프레임워크 | Next.js(App Router, `create-next-app@latest`) + TypeScript | 페이지 라우팅, 정적 생성, Vercel 배포 |
| 스타일 | Tailwind CSS | 빠른 레이아웃, 디자인 토큰 |
| 지도 | MapLibre GL JS + `react-map-gl/maplibre` | GeoJSON 레이어 + `circle-color-transition`으로 색 전환 애니메이션, 수천 점도 WebGL로 부드럽게 |
| 배경지도 타일 | 무료·키 없는 벡터 스타일(예: OpenFreeMap) 또는 MapTiler(키 필요) — **확인 필요**, 출처 표기 필수 | 점수 계산에 쓰지 않는 표시용 |
| 애니메이션 | Motion(`motion` 패키지, 구 Framer Motion) | 패널 슬라이드, 순위표 재정렬(layout 애니메이션), 숫자 카운트업 |
| 상태 | Zustand (가중치·선택 지역·선택 지점), URL 쿼리 동기화 | 시연용 상태를 링크로 공유 가능 |
| 데이터 로딩 | TanStack Query | 캐시·로딩 상태 처리 |
| 차트 | Recharts | 배경 통계, 민감도 분석 |
| UI 부품 | Radix UI(Slider, Dialog, Tabs, Tooltip) 또는 shadcn/ui | 접근성 있는 슬라이더·토글 |
| 테스트 | Vitest(골든 점수 테스트), Playwright(시연 시나리오 E2E, 선택) | |
| 배포 | Vercel | 정적 번들을 `public/data/`에 포함 |

> 배경지도 타일은 "데이터 소스 목록 밖"이지만 점수와 무관한 표시용이므로 리드 승인 항목으로 `docs/requests.md`에 기록하고 사용한다. 출처 표기는 지도 우하단에 상시 노출.

---

## 5. 데이터 소스

| ID | 데이터 | 용도 | 접근 | 저장 위치 | 상태 |
|---|---|---|---|---|---|
| D1 | 전국무료와이파이표준데이터 (15013116) | 지점 원장, 채점 입력 | CSV 수동 다운로드 (API 아님, 매일 갱신·2일 전 기준) | `backend/data/raw/snapshots/YYYY-MM-DD.csv` | 필수 |
| D2 | 구로구 공공와이파이 (15147901) `wifi접속환경` | R1 판정 검증 | 서울 열린데이터광장 수동 다운로드 | `backend/data/external/guro_wifi.csv` | 확인 필요 |
| D3 | 경찰청 사이버범죄 통계 (15053887) | 배경 패널 | 자동변환 API | `backend/data/external/police_cyber.csv` | 활용신청 |
| D4 | KISA 업종별 침해사고 (15155733) | 배경 패널 | 자동변환 API, 1회 수집 | `backend/data/external/kisa_industry.csv` | 활용신청 |
| D5 | KISA 민간 침해사고 (15140309) | 배경 패널 | API | `backend/data/external/kisa_private.csv` | 선택 |
| D6 | 뉴스 기반 사례 카드 | 사례 카드 | 수동 작성 | `backend/data/cases.yaml` | 출처·날짜 필수 |

- **API URL:** D3~D5의 실제 엔드포인트는 활용신청 후 data.go.kr Swagger 화면에서 복사해 `config/sources.yaml`·`.env`에 넣는다. 추측 URL 금지.
- **D1 예상 컬럼(최종 확인은 CSV 헤더로):** 설치장소명, 설치장소상세, 설치시도명, 설치시군구명, 설치시설구분, 서비스제공사명, 와이파이SSID, 설치연월, 소재지도로명주소, 소재지지번주소, 관리기관명, 관리기관전화번호, 위도, 경도, 데이터기준일자 → `schema.py`의 `COLUMN_MAP`으로 내부 영문 키에 매핑, 헤더 불일치 시 즉시 에러.
- **인코딩:** `utf-8-sig → cp949 → euc-kr` 순서로 시도.
- **수치 혼동 방지:** "6.9만 행"은 표준데이터 **행 수**, 기획안의 "4만7089곳"은 국회 제출 자료의 **설치 장소 수**(매일신문 2026-10-05). 같은 의미로 섞어 쓰지 않는다. census에서 둘 다 산출해 기록.

---

## 6. API 계약 (contracts/) — 두 담당의 경계선

**소유:** 담당 A. **버전:** `contracts/VERSION` (예: `1.0.0`). 필드 추가는 minor, 필드 삭제·의미 변경은 major + 상대 담당 확인 후 반영.

### 6.1 정적 번들 경로 (= API 경로와 1:1 대응)

| 정적 번들 파일 | FastAPI 엔드포인트 | 설명 |
|---|---|---|
| `data/meta.json` | `GET /api/meta` | 면책 문구, 데이터 기준일, R1 확정 여부, 계약 버전 |
| `data/rules.json` | `GET /api/rules` | R1~R8 메타데이터, 등급 경계, 파라미터 |
| `data/regions.json` | `GET /api/regions` | 시도·시군구 목록과 지점 수, 시연 기본 지역 |
| `data/points/{region_id}.json` | `GET /api/regions/{region_id}/points` | 지도용 경량 지점 목록 |
| `data/detail/{region_id}.json` | `GET /api/points/{key}` | 지점 상세(근거값·설명·수칙). API는 `key_index.json`으로 region을 찾아 해당 파일에서 꺼낸다 |
| `data/key_index.json` | (API 내부용, 공개 엔드포인트 없음) | `{ "a1b2c3d4": "11-guro", ... }` 지점 key → region_id 맵. 정적 번들에서도 key만으로 상세를 찾을 때 사용 |
| `data/changes/{region_id}.json` | `GET /api/regions/{region_id}/changes` | 추가·삭제 지점 |
| `data/sensitivity/{region_id}.json` | `GET /api/regions/{region_id}/sensitivity` | R1 30→15 순위 변화 |
| `data/background.json` | `GET /api/background` | 배경 통계(점수 미반영) |
| `data/cases.json` | `GET /api/cases` | 사례 카드 |
| — | `POST /api/points/{key}/explain` | 실시간 AI 설명(선택, 키 있을 때만) |

`region_id`는 `{시도코드}-{시군구명 슬러그}` 같은 안정적 ASCII 문자열(예: `11-guro`). 매핑은 `regions.json`에 포함.

### 6.2 스키마 예시

`meta.json`
```json
{
  "contract_version": "1.0.0",
  "disclaimer": "이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.",
  "r1_confirmed": false,
  "data_reference_date": "2026-10-18",
  "snapshot_collected_at": "2026-10-20",
  "sources": [
    {"id": "D1", "name": "전국무료와이파이표준데이터", "dataset_id": "15013116",
     "url": "https://www.data.go.kr/data/15013116/standard.do", "retrieved_at": "2026-10-20"}
  ]
}
```

`rules.json`
```json
{
  "rules": [
    {"id": "R1", "name": "보안접속 미지원", "max_points": 30, "is_assumption": false,
     "source_fields": ["ssid"], "one_liner": "SSID가 팀이 확정한 보안접속 목록에 없으면 위험요인으로 본다"}
  ],
  "grades": [
    {"min": 0, "max": 30, "label": "낮음", "emoji": "🟢", "color": "#2e9e5b"},
    {"min": 30, "max": 60, "label": "주의", "emoji": "🟡", "color": "#e0a800"},
    {"min": 60, "max": 101, "label": "높음", "emoji": "🔴", "color": "#d64545"}
  ],
  "params": {"MIN_SELECTED_RULES": 2, "LOW_MAXSUM_WARN": 30}
}
```

`points/{region_id}.json` — 지도용, 가볍게 유지
```json
{
  "region_id": "11-guro",
  "count": 2,
  "points": [
    {"key": "a1b2c3d4", "name": "OO버스정류장", "lat": 37.49, "lng": 126.88,
     "r": [1.0, 1.0, 1.0, 0.75, 0.4, 0.0, 0.0, 0.0],
     "score": 75.25, "grade": "높음", "flags": ["R4_assumption"]}
  ]
}
```
- `r`는 R1~R8 순서 고정 배열(0~1). `score`·`grade`는 기본 가중치 기준값.
- 검산: 30×1 + 20×1 + 10×1 + 15×0.75 + 10×0.4 + 0 + 0 + 0 = 75.25, 가중치 합 100 → **75.25**.

`detail/{region_id}.json` — `{ "a1b2c3d4": {...} }` 형태 맵
```json
{
  "key": "a1b2c3d4",
  "evidence": {"ssid": "Public WiFi Free", "facility_type": "교통시설", "place_detail": "버스정류장",
               "install_ym": "2017-03", "provider": "KT", "manager": "OO구청",
               "manager_tel": "02-000-0000", "data_date": "2026-10-18", "address": "..."},
  "breakdown": [{"id": "R1", "ratio": 1.0, "points": 30, "reason": "SSID가 개방형 목록에 있음"}],
  "explanation": {"text": "...", "source": "ai|template", "generated_at": "2026-10-21"},
  "safety_tips": ["같은 장소에 보안접속 SSID가 보이면 그쪽으로 연결하세요", "..."],
  "report_contact": {"manager": "OO구청", "tel": "02-000-0000"}
}
```

### 6.3 공용 채점 공식 (세 구현 모두 동일)

```
선택된 규칙 집합 S, 가중치 w_i, 위험비율 r_i
score = round(100 × Σ_{i∈S}(w_i × r_i) / Σ_{i∈S} w_i, 2)
grade = grades에서 min ≤ score < max 인 항목
|S| < MIN_SELECTED_RULES 이면 계산하지 않고 에러 상태
Σ_{i∈S} max_points_i < LOW_MAXSUM_WARN 이면 경고 표시(계산은 함)
가중치 합이 0이면 에러 상태
```

### 6.4 골든 테스트 파일

`contracts/golden_scores.json` (백엔드 `export_bundle.py`가 생성)
```json
{
  "cases": [
    {"r": [1,1,1,0.75,0.4,0,0,0], "weights": [30,20,10,15,10,5,5,5],
     "selected": [true,true,true,true,true,true,true,true], "expected_score": 75.25, "expected_grade": "높음"},
    {"r": [1,1,1,0.75,0.4,0,0,0], "weights": [15,20,10,15,10,5,5,5],
     "selected": [true,true,true,true,true,true,true,true], "expected_score": "자동 계산", "expected_grade": "자동 계산"}
  ]
}
```
→ 실제 파일은 경계값(29.99/30/59.99/60), 일부 선택, 가중치 0 케이스 포함 30건 이상을 자동 생성한다. 기대값은 사람이 손으로 쓰지 않고 `scoring.py`로 계산해 넣는다(위 예시처럼 손계산 오류가 섞이는 것을 막기 위함).

### 6.5 mock 데이터

`contracts/mock/`에 6.1과 같은 파일 구조로 가짜 지점 30~50개(가상의 지역 1곳)를 둔다. 파일 상단 `meta.json`에 `"is_mock": true`를 넣고, 프론트엔드는 이때 "샘플 데이터" 배지를 띄운다. **mock 값은 발표 화면에 절대 쓰지 않는다.**

---

## 7. 저장소 구조 (모노레포)

```
wifi-safety-map/
├── plan.md
├── README.md                       # 전체 실행법, 면책 문구, 데이터 출처
├── contracts/                      # ★ 경계선 (담당 A 소유)
│   ├── VERSION
│   ├── schemas/*.schema.json       # meta, rules, regions, points, detail, key_index, changes, sensitivity, background, cases (10종)
│   ├── golden_scores.json
│   └── mock/                       # 6.1과 동일 구조의 가짜 번들
├── backend/                        # ★ 담당 A
│   ├── requirements.txt
│   ├── .env.example                # DATA_GO_KR_KEY, ANTHROPIC_API_KEY, APP_MODE=dev|final, CORS_ORIGINS
│   ├── config/
│   │   ├── rules.py                # R1~R8 메타·기본 가중치·파라미터 (단일 진실 공급원)
│   │   ├── ssid_labels.csv         # SSID → open/secure/unknown (팀 확정 필수)
│   │   ├── facility_map.csv        # 설치시설구분 → R2 비율 + 사유
│   │   ├── keywords.yaml           # R3 실외 키워드, 금지 표현
│   │   └── sources.yaml
│   ├── data/
│   │   ├── raw/snapshots/          # 원본 스냅샷 + manifest.csv (수정 금지)
│   │   ├── external/
│   │   ├── interim/                # census 결과
│   │   ├── processed/              # wifi_clean.parquet, wifi_scored.csv, wifi_changes.csv, sensitivity_r1.csv
│   │   └── cases.yaml
│   ├── pipeline/
│   │   ├── ingest_snapshot.py
│   │   ├── census.py
│   │   ├── clean.py
│   │   ├── score.py
│   │   ├── changes.py
│   │   ├── sensitivity.py
│   │   ├── validate_guro.py
│   │   ├── fetch_background.py
│   │   ├── pregen_explanations.py  # 시연 지역 AI 설명 사전 생성
│   │   ├── ai_label_assist.py      # (선택) 분류 후보 생성, 확정은 사람
│   │   └── export_bundle.py        # ★ 정적 번들 + golden 생성, 스키마 검증
│   ├── src/wifisafe/
│   │   ├── schema.py  io.py  rules.py  density.py  scoring.py
│   │   ├── explain.py  guardrails.py  safety_tips.py
│   │   ├── background.py           # 점수 모듈과 분리
│   │   └── cases.py
│   ├── api/
│   │   ├── main.py                 # FastAPI 앱, CORS
│   │   ├── models.py               # 계약과 일치하는 pydantic 응답 모델
│   │   └── routes/                 # meta, rules, regions, points, changes, sensitivity, background, cases, explain
│   ├── dist/data/                  # export_bundle 출력 (정적 번들)
│   └── tests/
├── web-draft/                      # ★ 담당 A (정적 초안)
│   ├── index.html                  # 지도 + 사이드바 + 상세 패널
│   ├── rules.html                  # 채점 기준
│   ├── about.html                  # 데이터와 한계
│   ├── css/
│   │   ├── tokens.css              # 색·간격·폰트 토큰 (Next.js와 공유 기준)
│   │   └── main.css
│   ├── js/
│   │   ├── score.js                # 공용 채점 공식
│   │   ├── api.js                  # 번들 fetch (경로 상수 하나로 mock/실데이터 전환)
│   │   ├── map.js                  # Leaflet 마커
│   │   ├── panel.js                # 상세 패널, 순위표
│   │   └── main.js
│   ├── data/                       # backend/dist/data 복사본 (스크립트로 동기화)
│   └── tests/score.test.html       # golden_scores.json으로 브라우저 내 검증
├── frontend/                       # ★ 담당 B (Next.js)
│   └── (§9 구조)
├── scripts/
│   ├── sync_bundle.sh / .ps1       # backend/dist/data → web-draft/data, frontend/public/data
│   └── check_disclaimer.py         # 세 앱의 화면 소스에 면책 문구 컴포넌트 사용 여부 검사
└── docs/
    ├── progress.md  requests.md  slides_outline.md  demo_script.md
```

---

## 8. 백엔드 상세 (담당 A)

### 8.1 `config/rules.py`

```python
# 모든 가중치·파라미터는 여기서만 정의한다. rules.json, 채점표, 슬라이더 기본값이 모두 여기서 나온다.
from dataclasses import dataclass

DISCLAIMER = "이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다."

@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    max_points: int
    source_fields: tuple
    is_assumption: bool
    one_liner: str   # 발표 1줄 설명. 1줄로 못 쓰면 규칙 삭제(투명성 원칙)

RULES = (
    Rule("R1", "보안접속 미지원", 30, ("ssid",), False,
         "SSID가 팀이 확정한 보안접속 목록에 없으면 위험요인으로 본다"),
    Rule("R2", "시설유형", 20, ("facility_type",), True,
         "불특정 다수가 오가는 시설일수록 높게 본다"),
    Rule("R3", "실외", 10, ("place_detail", "facility_type"), True,
         "설치장소 문구에 실외 키워드가 있으면 위험요인으로 본다"),
    Rule("R4", "노후도", 15, ("install_ym",), True,
         "설치 후 오래될수록 장비 보안 수준이 낮을 수 있다고 가정한다"),
    Rule("R5", "개방형 AP 밀집도", 10, ("lat", "lng", "ssid"), False,
         "반경 100m 안 개방형 AP가 많을수록 위장 AP가 섞이기 쉽다"),
    Rule("R6", "제공주체 불명", 5, ("provider", "manager"), False,
         "제공사·관리기관 정보가 비어 있으면 위험요인으로 본다"),
    Rule("R7", "신고경로 부재", 5, ("manager_tel",), False,
         "관리기관 전화번호가 없거나 형식이 틀리면 위험요인으로 본다"),
    Rule("R8", "데이터 노후", 5, ("data_date",), False,
         "데이터 기준일자가 오래되면 운영 상태를 신뢰하기 어렵다"),
)

GRADES = ((0, 30, "낮음", "🟢", "#2e9e5b"),
          (30, 60, "주의", "🟡", "#e0a800"),
          (60, 101, "높음", "🔴", "#d64545"))

PARAMS = {
    "R1_UNKNOWN_RATIO": 0.5,   # 가정
    "R4_FULL_YEARS": 8,        # 가정
    "R4_MISSING_RATIO": 0.5,   # 가정, '결측' flag
    "R5_RADIUS_M": 100,
    "R5_FULL_COUNT": 5,
    "R8_WARN_DAYS": 180,
    "R8_STALE_DAYS": 365,
    "MIN_SELECTED_RULES": 2,
    "LOW_MAXSUM_WARN": 30,
}
```

### 8.2 규칙별 판정 로직

| 규칙 | 입력 | 판정 → `r_i` | 가정 |
|---|---|---|---|
| R1 | ssid | `ssid_labels.csv`: open→1.0, secure→0.0, unknown→0.5 | 라벨 확정 전 무효 |
| R2 | facility_type | `facility_map.csv`(값별 0/0.25/0.5/1.0 + 사유). 미등록→0.5 + flag | 가정 |
| R3 | place_detail, facility_type | 실외 키워드(정류장, 공원, 광장, 거리, 시장, 실외, 야외 등 — census 후 확정) 포함→1.0 | 가정 |
| R4 | install_ym | 경과연수 / R4_FULL_YEARS, 0~1. 결측→0.5 + flag | 가정 |
| R5 | lat, lng, ssid | 같은 시군구 내 반경 100m 개방형 AP 수(자신 제외) / R5_FULL_COUNT, 0~1 | — (단, **시군구 경계 한계**: 경계 100m 이내 지점은 이웃 시군구 AP를 세지 않아 과소평가될 수 있음. 해당 지점은 `R5_boundary` flag, /about에 명시) |
| R6 | provider, manager | 둘 다 결측·"미상"·"기타"→1.0, 하나만→0.5 | — |
| R7 | manager_tel | 결측 또는 전화번호 정규식 불일치→1.0 | — |
| R8 | data_date | 경과일 ≥365→1.0, ≥180→0.5 | — |

### 8.3 R1 확정 절차 (최우선)

1. `census.py` → `interim/ssid_census.csv` (SSID 고유값, 빈도, 예시 시군구)
2. (선택) `ai_label_assist.py`로 후보 라벨 — 후보일 뿐
3. 상위 빈도부터 수동 라벨링 → `ssid_labels.csv` (`ssid, label, evidence, reviewer, reviewed_at, status`)
4. 리드 검토 후 `status=confirmed`, 행 기준 커버리지 기록
5. `validate_guro.py`로 구로구 `wifi접속환경`과 일치율 산출 → 발표 검증 슬라이드

`APP_MODE=final`에서 미확정 라벨이 있으면 `score.py`·`export_bundle.py`는 에러로 종료.

### 8.4 AI 설명 (`explain.py`)

```python
SYSTEM_PROMPT = """너는 공공와이파이 지점의 위험요인 점수를 시민에게 설명하는 안내문 작성자다.
규칙:
- 아래 JSON에 있는 값만 인용한다. 새로운 수치·사건·통계를 만들지 않는다.
- 2~3문장, 존댓말, 쉬운 단어.
- '해킹 확률', '해킹될 확률', '위험 지역' 같은 표현을 쓰지 않는다.
- 점수가 높은 항목 1~2개의 이유를 근거값과 함께 말하고, 마지막 문장은 행동 하나를 권한다."""
```
검증(하나라도 실패 시 템플릿 사용): ① 금지 표현 0 ② 출력 속 모든 숫자가 입력 값 집합에 존재 ③ 문장 2~3개.
템플릿: `"{place}의 위험요인 점수는 {score}점({grade})입니다. 가장 큰 요인은 {top1_name}({top1_evidence})입니다. {tip}"`
키가 없으면 템플릿만 사용. 시연 지역은 `pregen_explanations.py`로 사전 생성해 번들에 포함.

### 8.5 스냅샷·변경 이력

- 고유 ID 컬럼이 없으면 키 = `sha1(round(lat,5), round(lng,5), ssid, place_name)` 앞 8~12자.
- `ingest_snapshot.py <파일>` → `snapshots/YYYY-MM-DD.csv` 복사 + `manifest.csv`(해시·행 수·데이터 기준일자).
- `changes.py` → `wifi_changes.csv`: `snapshot_from, snapshot_to, key, change(added|removed), sido, sigungu, place_name, ssid, lat, lng`.
- 주 1회 기준(최소 3~4회). 마감까지 4주가 안 남으면 2~3일 간격으로 수집하고 발표엔 "N회 수집, 기간 X~Y"로 표기.

### 8.6 민감도 분석

기준 A(기본) vs 기준 B(R1=15). 출력 `sensitivity_r1.csv`: `key, place_name, rank_A, rank_B, delta, score_A, score_B, grade_A, grade_B` + 요약(상위 20 겹침 수, 스피어만 상관, 등급 이동 건수).

### 8.7 FastAPI

- `api/main.py`: CORS(`CORS_ORIGINS` env), `/api/*` 라우트, `/docs` 자동 문서.
- 응답은 `backend/dist/data`의 번들을 그대로 읽어 반환(로직 중복 방지). `/explain`만 실시간 처리 + 결과 캐시.
- 시작 시 `key_index.json`을 메모리에 올리고, `GET /api/points/{key}`는 key → region_id → `detail/{region_id}.json` 순서로 조회한다. 인덱스에 없는 key는 404.
- 모든 응답 헤더에 `X-Disclaimer`(URL 인코딩된 면책 문구) 추가.

---

## 9. Next.js 프론트엔드 상세 (담당 B)

### 9.1 폴더 구조

```
frontend/
├── .env.local.example        # NEXT_PUBLIC_DATA_BASE=/data (정적) | http://localhost:8000/api (API) | /mock
├── public/data/              # sync_bundle로 복사된 정적 번들
├── src/
│   ├── app/
│   │   ├── layout.tsx        # DisclaimerBar 고정, 폰트, 테마
│   │   ├── page.tsx          # 랜딩: 문제 한 줄 + 페르소나 장면 + "지도 열기"
│   │   ├── map/page.tsx      # ★ 메인 지도 화면
│   │   ├── rules/page.tsx    # 채점 기준 (rules.json으로 자동 생성)
│   │   ├── sensitivity/page.tsx
│   │   ├── context/page.tsx  # 배경 통계·사례 카드 ("점수 미반영" 고정)
│   │   └── about/page.tsx    # 데이터와 한계
│   ├── components/
│   │   ├── DisclaimerBar.tsx
│   │   ├── RegionPicker.tsx
│   │   ├── WeightPanel.tsx       # 체크박스 + 슬라이더 + 기본값 복원
│   │   ├── MapCanvas.tsx         # MapLibre, GeoJSON source, circle layer
│   │   ├── PointSheet.tsx        # 지점 상세 슬라이드 패널
│   │   ├── ScoreBreakdown.tsx    # R1~R8 막대
│   │   ├── RankTable.tsx         # 순위 변동 표 (layout 애니메이션)
│   │   ├── SafetyChecklist.tsx
│   │   ├── LayerToggle.tsx
│   │   ├── AssumptionBadge.tsx  MockBadge.tsx  ProvisionalWatermark.tsx
│   │   └── SourceNote.tsx        # 출처·날짜 표기 공용
│   ├── lib/
│   │   ├── score.ts              # 공용 채점 공식 (§6.3)
│   │   ├── api.ts                # NEXT_PUBLIC_DATA_BASE 기반 fetch, 정적/API 경로 매핑
│   │   ├── types.ts              # contracts/schemas에서 생성한 타입
│   │   └── guardrails.ts         # 금지 표현 검사(AI 실시간 응답 표시 전)
│   ├── store/useAppStore.ts      # 지역, 가중치, 선택 규칙, 선택 지점, 레이어 (URL 쿼리 동기화)
│   └── styles/tokens.css         # web-draft/css/tokens.css와 같은 값
└── tests/
    ├── score.golden.test.ts      # contracts/golden_scores.json 통과 필수
    └── e2e/demo.spec.ts          # (선택) 시연 시나리오 Playwright
```

타입 생성: `json-schema-to-typescript`로 `contracts/schemas/*.schema.json` → `src/lib/types.ts` (`npm run gen:types`).

### 9.2 동작 효과 설계 ("동적이고 자연스럽게"의 구체 정의)

| 장면 | 효과 | 구현 | 목적 |
|---|---|---|---|
| 지역 선택 | 지도가 해당 시군구로 `flyTo`(약 1.2초), 마커가 작은 크기에서 커지며 등장 | MapLibre `flyTo`, `circle-radius-transition` | 장소 전환을 자연스럽게 |
| 슬라이더 조작 | 마커 색이 0.4초 동안 부드럽게 전환, 등급 개수 숫자 카운트업 | `circle-color-transition`, Motion `animate` | "기준이 바뀌면 점수가 바뀐다"를 눈으로 |
| 순위 변동 표 | 행이 위아래로 미끄러지며 재정렬, ▲▼ 색 플래시 | Motion `layout` + `AnimatePresence` | 민감도를 직관적으로 |
| 지점 클릭 | 선택 마커 펄스 링, 오른쪽(모바일은 아래)에서 상세 패널 슬라이드 인 | Motion spring, 별도 하이라이트 레이어 | 집중 유도 |
| 항목 점수 | R1~R8 막대가 순서대로 채워짐(stagger 50ms) | Motion variants | 근거 구조 전달 |
| AI 설명 | 스켈레톤 → 문장 단위 페이드 인 | Motion | 생성 대기감 완화 |
| 레이어 토글 | 추가 지점 초록 테두리 펄스, 삭제 지점 회색 점선 페이드 | 별도 circle 레이어 + opacity transition | 변화 이력 강조 |

**규칙:**
- 슬라이더 입력은 `requestAnimationFrame` 또는 100~150ms 디바운스 후 재채점. 재채점 결과는 GeoJSON `setData` 대신 feature property 갱신(또는 `setFeatureState`)으로 깜빡임 없이.
- `prefers-reduced-motion`이면 모든 전환을 즉시 적용.
- 면책 배너는 애니메이션 대상이 아니다(항상 고정·즉시 표시).
- 애니메이션 때문에 시연 지역에서 첫 화면 표시가 3초를 넘으면 효과를 줄인다.

### 9.3 화면별 요구사항

**/map**
- 좌측(데스크톱) 패널: RegionPicker(기본: `regions.json`의 시연 지역) → WeightPanel → LayerToggle → 등급 필터
- WeightPanel: R1~R8 각 [체크] + [슬라이더 0~2×max] + 가정 배지, "기본값으로" 버튼. 선택 2개 미만이면 지도 위 안내 오버레이 + 계산 중지, 만점 합 < 30이면 노란 경고
- 상단 요약: 지점 수, 등급별 개수, 평균 점수
- 하단/우측: RankTable(기본 상위 20 vs 현재 상위 20, 겹침 수)
- 장소명 검색 콤보박스(클릭 실패 대비 시연 보조)
- `meta.r1_confirmed=false`면 지도 전체에 "임시(무효)" 워터마크, `is_mock=true`면 "샘플 데이터" 배지

**/rules** — rules.json으로 표 자동 생성(ID·이름·만점·근거 필드·가정·1줄 설명) + 등급 기준. 발표 채점표 캡처용으로 깔끔하게.
**/sensitivity** — 순위 변화 표, 요약 지표 카드, 산점도(rank_A vs rank_B).
**/context** — 배경 통계 차트(각 차트 아래 SourceNote), 사례 카드(“같은 원리 사례 — 국내 공공와이파이 사건 아님” 라벨). 상단 "이 통계는 지점 점수에 반영하지 않습니다" 고정.
**/about** — 데이터 출처 표, 지점 단위 해킹 사건 공공데이터 부재(확인 기준일 2026-10-20), 가정 목록, 시군구 경계 한계(R5 밀집도는 같은 시군구 AP만 세므로 경계 근처 지점은 낮게 나올 수 있음), 최근 60일 국내 공공와이파이 해킹 보도 부재를 그대로 명시.

### 9.4 반응형·접근성

- 데스크톱(발표 프로젝터 1920×1080) 우선, 모바일은 패널이 바텀시트로.
- 등급은 색만으로 구분하지 않는다(이모지·텍스트 병기, 색각 이상 고려).
- 슬라이더는 키보드 조작 가능(Radix Slider).

---

## 10. 정적 초안 상세 (담당 A, `web-draft/`)

- **목표:** 하루 안에 흐름 1~3(지역 선택 → 마커 → 클릭 상세 → 슬라이더 재채점·순위표)이 동작하는 단일 페이지.
- **레이아웃:** 상단 면책 배너 / 좌측 사이드바(지역·슬라이더) / 중앙 지도 / 우측 상세 패널. Next.js가 그대로 참고할 수 있게 영역 이름을 §9 컴포넌트 이름과 맞춘다(`.weight-panel`, `.point-sheet`, `.rank-table`).
- **동작:** CSS `transition`으로 패널 슬라이드·마커 색 변경(Leaflet `circleMarker.setStyle`) 정도의 가벼운 효과만. 화려한 효과는 Next.js 몫.
- **`js/score.js`:** §6.3 공식. `tests/score.test.html`이 `golden_scores.json`을 불러와 전부 통과해야 함.
- **데이터 경로:** `js/api.js`의 `DATA_BASE` 상수 하나로 `./data`(실데이터)와 `../contracts/mock`(mock) 전환.
- **백업 데모 조건:** 인터넷이 없어도 지도 타일 외 기능이 동작해야 함 → 시연 지역 번들을 `web-draft/data/`에 포함.

---

## 11. 개발 일정 (병렬 레인, 상대 일자 — 마감 2026-10-21 16:00 KST)

| 일차 | 담당 A (백엔드 + 정적 초안) | 담당 B (Next.js) | 동기화 지점 |
|---|---|---|---|
| D1 오전 | 저장소 생성, `contracts/` 스키마 v1.0(10종) + mock + golden(mock 기반) → **정오까지 B에게 전달** | Next.js 생성, Tailwind·MapLibre·Motion 설치 | ✅ 계약 v1.0 동결(정오) |
| D1 오후 | **첫 CSV 스냅샷 등록**, COLUMN_MAP 확정, census | mock으로 /map 뼈대 + DisclaimerBar | — |
| D2 | SSID·시설 라벨 확정(리드와 함께), clean·score | WeightPanel + score.ts + 골든 테스트 통과, MapCanvas 마커 색 | ✅ 골든 테스트 양쪽 통과 |
| D3 | export_bundle(실데이터 dev 번들), FastAPI, 정적 초안 흐름 1~3 | PointSheet, RankTable, 동작 효과 1차 | ✅ 실데이터 번들로 B 전환 |
| D4 | changes·sensitivity·validate_guro·fetch_background·cases, AI 설명 사전 생성 | /rules /sensitivity /context /about, LayerToggle | ✅ 전체 엔드포인트 연결 |
| D5 | final 번들(R1 확정), 버그 수정, 정적 초안 백업 점검 | 애니메이션 다듬기, 반응형, Vercel 배포 | ✅ 시연 리허설 2회 |
| D6 | 발표자료 수치 확정(출처·날짜) | 시연 시나리오 E2E 확인 | ✅ 최종 동결 |

스냅샷 수집은 D1부터 일정 간격으로 계속(§8.5).

---

## 12. 마일스톤과 수용 기준

| 단계 | 담당 | 수용 기준 |
|---|---|---|
| M0 계약 | A | 스키마 10종 + mock + golden 존재, `jsonschema`로 mock 검증 통과, D1 정오까지 B에게 전달 |
| M1 census | A | 실제 헤더로 COLUMN_MAP 확정, SSID·시설 census 생성, 행 수/고유 장소 수 기록 |
| M2 라벨 | A+리드 | SSID 라벨 커버리지(행 기준) 95% 이상 또는 미달 사유 기록, `status=confirmed` |
| M3 채점·번들 | A | `wifi_scored.csv` 생성, r_i ∈ [0,1], 번들 스키마 검증 통과, golden 실데이터 버전 갱신 |
| M4a 정적 초안 | A | 흐름 1~3 동작, `score.test.html` 전부 통과, 오프라인(타일 제외) 동작 |
| M4b Next.js 핵심 | B | mock→실데이터 전환이 env 하나로 됨, 골든 테스트 통과, 슬라이더 조작 시 색·순위 갱신, 2개 미만 선택 차단 |
| M5 부가 | A+B | 변경 레이어·민감도·배경·사례 페이지 동작, 출처 없는 사례 로드 시 에러, AI 설명 샘플 20건 금지어 0·근거 외 수치 0 |
| M6 배포·시연 | B(+A) | Vercel URL에서 시연 시나리오 전체 재현, API 서버 꺼도 정상 동작, 정적 초안 백업 동작 확인 |

---

## 13. 테스트 목록

| 위치 | 검사 |
|---|---|
| backend/tests/test_rules.py | R4 0년/8년/결측, R8 179/180/365일, R7 전화번호 형식, r_i 범위 |
| backend/tests/test_scoring.py | 기본 총점 = Σ(max×r), 선택 2개 미만·가중치 합 0 에러, 등급 경계 29.99/30/59.99/60 |
| backend/tests/test_guardrails.py | 금지 표현, 면책 문구 부정형 허용, AI 숫자 검증 |
| backend/tests/test_isolation.py | scoring·rules가 background 모듈을 import하지 않음 |
| backend/tests/test_bundle.py | 번들 전 파일 스키마 검증, meta에 disclaimer 존재, `key_index.json`의 key가 모든 `points/*.json` key와 1:1 일치 |
| backend/tests/test_api.py | `GET /api/points/{key}` 정상 조회, 없는 key 404 |
| web-draft/tests/score.test.html | golden 전부 통과 |
| frontend/tests/score.golden.test.ts | golden 전부 통과 |
| scripts/check_disclaimer.py | Next.js layout·초안 각 HTML에 면책 배너 존재 |

---

## 14. 실행 방법 (README에 그대로 복사)

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
python pipeline/sensitivity.py --sigungu 구로구
python pipeline/export_bundle.py --regions 11-guro        # dist/data + contracts/golden 갱신
uvicorn api.main:app --reload --port 8000                 # 선택: API 서버

cd .. && bash scripts/sync_bundle.sh                      # Windows: scripts\sync_bundle.ps1

# ── 정적 초안 (담당 A) ──
cd web-draft && python -m http.server 5500                # http://localhost:5500

# ── Next.js (담당 B) ──
cd frontend
npm install
cp .env.local.example .env.local                          # NEXT_PUBLIC_DATA_BASE=/data
npm run gen:types
npm test
npm run dev                                               # http://localhost:3000
```

`backend/requirements.txt` 초안(설치 후 `pip freeze`로 버전 고정):
```
pandas
pyarrow
scikit-learn
pydantic
pyyaml
jsonschema
python-dotenv
fastapi
uvicorn
anthropic
pytest
```

`frontend` 주요 패키지 초안: `maplibre-gl react-map-gl motion zustand @tanstack/react-query recharts @radix-ui/react-slider` / dev: `vitest json-schema-to-typescript @playwright/test`

---

## 15. 리스크와 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| SSID만으로 보안접속 여부가 안 갈림 | R1 무효 → 점수표 전체 무효 | unknown 0.5 처리 + 가정 라벨, 구로구 일치율로 검증 수치 제시 |
| 세 곳의 채점 공식 불일치 | 화면마다 점수가 다름 | golden 테스트를 세 구현의 필수 통과 조건으로 |
| 계약 변경으로 B 작업 깨짐 | 일정 지연 | D1 계약 동결, 변경은 버전 올리고 합의 후 |
| B가 실데이터를 늦게 받음 | 통합 지연 | mock으로 선개발, env 전환만으로 교체 |
| Next.js 애니메이션 과욕 | 핵심 기능 미완성 | M4b(핵심) 통과 전 §9.2 효과 작업 금지, 효과는 D4~D5에 |
| API 서버 콜드스타트·장애 | 시연 실패 | 시연은 정적 번들, AI 설명 사전 생성, 정적 초안 백업 |
| 배경지도 타일 서비스 제한·키 문제 | 지도 배경 미표시 | 사전 리허설로 확인, 대체 타일 1개 준비, 출처 표기 |
| 15053887이 시도별 통계가 아님 | 지도 배경 레이어 불가 | 지도 레이어는 "추가·삭제 지점"으로 충족, 범죄 통계는 /context 차트로. 시도 경계 GeoJSON은 리드 승인 필요 |
| R5 시군구 경계 효과 | 경계 근처 지점 밀집도 과소평가 | `R5_boundary` flag, /about에 한계 명시. 전국 단위 계산은 확장 과제로 |
| D1 작업 과밀 | B가 계약을 늦게 받아 병렬 개발 지연 | 계약·mock을 D1 오전에 먼저 넘기고 수집·census는 오후로 |
| 스냅샷 횟수 부족 | wifi_changes DoD 미달 | D1부터 수집, 간격 단축, 수집 횟수 사실대로 표기 |
| AI 설명이 근거 밖 내용 생성 | 신뢰도 하락 | 금지어·숫자 검증 후 템플릿 폴백 |
| 최근 국내 공공와이파이 해킹 보도 없음 | 시급성 공격받음 | /about에 그대로 명시, 같은 원리 사례는 "같은 원리 사례" 라벨 |

---

## 16. 발표 연결 (`docs/slides_outline.md`)

1. 문제정의 — 버스정류장 학생 페르소나, 면책 문구
2. 데이터 한계 — 지점 단위 사건 데이터 없음(2026-10-20 확인) → 그래서 "위험요인 지표"
3. 채점표 — `/rules` 화면 캡처(가정 배지 포함)
4. 검증 — 구로구 접속환경 일치율, AI 설명 검수 결과
5. 민감도 분석 — R1 30→15 순위 변화 1컷
6. 데모 — ① 구로구 선택(flyTo) ② '높음' 지점 클릭 → 상세·근거 ③ 보안접속·밀집도만 체크 → 색 전환·순위 재정렬 ④ 추가·삭제 레이어 ⑤ 안전수칙
7. 한계와 다음 단계

시연 순서·대사·백업 전환 절차는 `docs/demo_script.md`에 별도 작성(Next.js 장애 시 정적 초안 URL로 즉시 전환).

---

## 17. 열린 질문 (확인 후 이 문서 갱신)

> 2026-10-21 갱신. 근거는 `docs/requests.md` 번호.

- [x] D1 실제 헤더명과 고유 ID 컬럼 존재 여부 → 20개 컬럼, 고유 ID `관리번호` 있음. 원본은 LOCALDATA 전국 파일 매일 자동 수집으로 바뀜(#15)
- [x] 설치시설구분 값 체계(코드값/텍스트) → 텍스트 8종(교통시설·관광·편의시설·기타·지역문화시설·관공서·서민·복지시설·교육시설), 비율 확정(#21)
- [x] 15053887의 지역 단위(시도별 여부) → 전국 단일 파일(LOCALDATA, 94,166행). 시도명 `전남광주통합특별시`는 행안부 코드 12로 등록(#37)
- [x] 구로구 15147901 `wifi접속환경` 값 종류와 D1 매칭 키 → 받은 파일에 컬럼 없음. 서울 열린데이터광장 API의 실내외 구분으로 R3 일치율 검증으로 변경(#12·#28, 키 발급 대기)
- [x] 배경지도 타일 최종 선택 → 카카오맵 JavaScript SDK(#31). web-draft는 키 없을 때 OSM 대체
- [x] 시연 지역 최종 확정 → 기본 고양시(41-goyang), 정적 백업 고양·서초·구로(#34)
- [x] 해커톤 마감일 → **2026-10-21(수) 16:00 KST** 발표. §11 상대 일정은 지난 일정이라 그대로 두고, 남은 일은 `docs/progress.md` 마감 체크리스트로 관리
