# 진행 기록 (마일스톤 수용 기준 실행 결과)

## M0 계약 — 2026-10-20 ✅

- 스키마 10종(`contracts/schemas/`) + `_common` 공용 정의, `contracts/VERSION` = 1.0.0
- mock 번들(`contracts/mock/`, 가상 지역 `99-gasang`, 40개 지점, 스냅샷 2회·변경 6건): `python pipeline/make_mock.py` → **jsonschema 검증 통과**
- golden 51건(경계 29.99/30/59.99/60, 부분 선택, 가중치 0, 선택 1개·0개, 저합계 경고, mock 샘플 30건)
- 검산: plan 예시 `r=[1,1,1,0.75,0.4,0,0,0]` 기본 가중치 → **75.25 (높음)**, R1=15 → 70.88
- 교차 검증: Python `pytest` 73건 통과, `node web-draft/tests/score.test.mjs` 51/51, 브라우저 `score.test.html` 51/51
- [ ] 담당 B에게 전달(contracts/README.md 공유) — 사용자 확인 필요

## M1 census — 2026-10-20 ✅ (시도코드 1건은 임시 제외)

- 첫 스냅샷 등록: `무료와이파이정보.csv` → `snapshots/2026-10-20.csv` (cp949, **94,166행**, 데이터기준일자 2013-06-30 ~ 2026-09-30)
  - plan의 "6.9만 행"과 다름 → 발표 수치는 이 스냅샷 기준으로 다시 쓴다
- ✅ 실제 헤더로 `COLUMN_MAP` 확정: `설치시설구분명`, `WGS84위도`, `WGS84경도`로 수정, 고유 ID `관리번호`(중복 0)
- ✅ 행 수 94,166 / 고유 장소(시도·시군구·장소명·주소) 62,654 / 고유 좌표 57,470 / 고유 SSID 1,093 / 시설구분 8종
- ✅ census 산출물: `data/interim/ssid_census.csv`, `facility_census.csv`, `place_detail_census.csv`, `census_summary.json`
- 발견 사항
  - SSID 빈값 27,616행(29.3%) → 제외하지 않고 R1 '불명'(가정 0.5) + `R1_ssid_missing` flag
  - 한 칸에 SSID 여러 개(쉼표 구분) 4,265행, 예: `SEOUL, SEOUL_Secure`
  - **구로구 1,259행 전부 SSID = `SEOUL, SEOUL_Secure`** → 시연 지역에서 R1·R5가 모든 지점에서 같은 값이 됨
  - 시도명 `전남광주통합특별시`(9,546행) 시도코드 미등록 → **공식 코드 확인 전까지 clean에서 제외, 경고 출력**(사용자 결정 2026-10-20, `schema.py PENDING_SIDO`) → **2026-10-21 공식 코드 12 확인·등록, 포함**(requests #37)
  - D2 구로구 파일에 `wifi접속환경` 컬럼 없음(실내외구분·서비스구분·망종류는 있음), X좌표=위도·Y좌표=경도

### clean·score 1차 실행 (2026-10-20, APP_MODE=dev, 라벨 미확정 → 점수는 임시·무효)

- clean: 94,166행 → **84,599행**, 시군구 201개 (좌표 뒤바뀜 수정 3, 좌표 불량 제외 21, 전남광주통합특별시 제외 9,546, 중복 0)
- region_id 충돌 없음(접미사 붙은 id 0개), 구로구 = `11-guro`
- score 구로구 1,259행: r_i∈[0,1] 확인, 점수 26.5 ~ 49.94(중앙 34.31), 등급 주의 1,067 / 낮음 192 / 높음 0
  - R1·R2가 라벨 미확정이라 전 지점 0.5(가정)로 고정, R5는 개방형 라벨이 없어 0 → 라벨 확정 후 다시 채점
  - R3 실외 판정 3.3%뿐: 구로구 설치장소상세 상위가 '가로등주', '아케이드 기둥', '안양천' 등 → 실외 키워드 보강 필요(M2)
  - R8: 구로구 데이터기준일자 전부 2026-05-18(기준일로부터 155일) → 0
- 전국: 주의 82,822 / 낮음 1,777, R1 flag = 라벨 없음 60,365 · SSID 빈값 24,234

## M2 라벨 — 후보 초안 생성, 사람 검토 대기

- 2026-10-20 `pipeline/draft_ssid_labels.py`(이름 규칙만 사용, AI 미사용) → `config/ssid_labels_candidates.csv` 1,092건, 전부 `status=candidate`
  - 상위 96개가 SSID 있는 행(66,550)의 95%
  - 후보: open 44,136행 / secure 6,093행 / unknown 16,321행, 신뢰도 높음 29,154 · 중간 15,742 · 낮음 16,612 · 검토필요(혼합) 5,042
- 커버리지 기준: SSID 빈값 27,616행은 라벨을 붙일 수 없으므로 **SSID 있는 행 기준**으로 측정(`coverage_confirmed_nonempty`)
- 리드 결정 필요: 혼합 칸(예: `SEOUL, SEOUL_Secure`)을 secure로 볼지 — 구로구 전 지점이 해당
- [x] 검토 후 `config/ssid_labels.csv` 반영: 상위 96개 확정, SSID 있는 행 기준 95.1% (#22·#25·#26)
- 2026-10-20 사용자 결정: MIXED 칸 → secure (requests #14), SSID 빈값 0.5 유지(#10), R8 결측 1.0 유지(#8), 저합계 경고 기준 유지(#6)
- R3 실외 키워드 후보 28개 + 실내 우선 10개 → `config/r3_keyword_candidates.csv`, `keywords.yaml`에 **초안 적용**(r3_status: draft)
  - R3 실외 판정 비율: 전국 18.3% → 26.9%, 구로구 3.3% → 41.1% (참고: 구로구 D2 `실내외구분` 실외 66.8%)
- 시연 지역 비교표(후보 라벨 기준, 임시): `docs/region_comparison.md`
  - 구로구: 후보 라벨 기준 R1 100% secure, R5 0% → 등급 주의 213 / 낮음 1,046, 높음 0
- [x] `config/facility_map.csv`(R2) 확정 (#21, 구로구 점수 표준편차 5.81 → 8.91)
- [x] `keywords.yaml` R3 실외 키워드 28개 확정, 실내 예외어 감시실·시장실 추가 (#27)
- [x] R1 게이트를 지역별(확정 비율 90%)로, SSID 없는 지역은 'SSID 정보 없음' (#23·#24) — 2026-10-21 수집 기준 확정 125 · 임시 45 · SSID 없음 58
- [x] `Public WiFi Free`만 적힌 칸 → 불명 0.5, flag `R1_free_only` (#47, 2026-10-21)
- [x] WiGLE 표본 검증 시도(일일 한도로 판단 가능 1곳) + 대전 서구 둔산동 현장 확인 → `Public_WiFi_Free` secure (#48, [wigle_validation.md](wigle_validation.md))

## M3 채점·번들 — 2026-10-21 ✅
- 실데이터 전국 채점, Neon `bundle_docs` 저장(`pipeline/daily_sync.py`), 정적 백업 번들 고양·서초·구로(기본 고양시, #34)
- 좌표 이상: bbox 바깥 2% 제외(#32), 같은 간격 일직선 좌표 `COORD_suspect`(대전 서구 302곳, #38)
- 설명문: 근거값 기반 템플릿, 요인 최대 2개(#36) — 2,902건 가드레일 실패 0
- 등급 색 변경(#44): rules.py·DB·번들·mock·golden 동일 반영

## M4 화면 — 2026-10-21 ✅
- Next.js 16 + 카카오맵(`frontend/`) 배포, web-draft는 인터넷 없는 백업 시연용
- API 장애 시 정적 번들 자동 전환, 5분 뒤 자동 복귀·"다시 시도" 버튼
- 디자인 개편: 지도(#44), 채점 기준 KaTeX(#45), 민감도 토네이도·생키(#46), 메뉴·소개·배경 통계(`e10059c`)
- "내 위치": GPS 대신 지도를 눌러 직접 지정(`bb275cd`)
- 같은 좌표 AP를 마커 1개로 묶음(겹친 마커 색이 순위표·상세 점수와 어긋나던 문제), 상세에서 같은 장소 AP 전환, 마우스 올림 라벨에 이름·최고 점수(`520eef6`, `a8cb50b`)
- 같은 좌표 묶음 마커의 대표를 점수가 가장 낮은 AP로 변경(라벨 최저 점수, 상세의 같은 장소 목록도 점수 낮은 순) — 2026-10-22

## M5 부가 — 2026-10-21 ✅ (R3 검증 제외)
- 배경 통계 2종(#30), 사례 카드 4건 요약 반영(#40)
- [ ] 서울 API로 R3 실내외 일치율 검증(#28) — 키 발급 대기
- [ ] WiGLE 표본 50곳 채우기 — 하루 한도 때문에 여러 날 필요(같은 스크립트 재실행 시 이어서 진행)

## 마감 체크리스트 (발표 2026-10-21 16:00 KST)
- [x] 커밋(feat/decisions-and-frontend) → main 병합 → GitHub 푸시
- [x] Vercel 배포(2026-10-21): API https://wifi-traffic-api.vercel.app (sin1, Neon), 화면 https://wifi-traffic.vercel.app — backend API(환경변수 DATABASE_URL·SESSION_SECRET·GOOGLE_CLIENT_ID·CORS_ORIGINS), frontend(NEXT_PUBLIC_*)
- [ ] GitHub Secret `DATABASE_URL`(매일 수집 Actions)
- [x] 카카오(JS SDK 도메인)·구글(승인된 자바스크립트 원본)·네이버(서비스 URL·Callback)에 배포 주소 등록
- [x] 배포 주소 확인: 비회원 → 고양시 613곳·카카오맵, 검색·지점 상세·대전 서구 처음 화면·배경 통계 차트·사례 4건 · 배포 주소 구글·네이버 실제 로그인 사용자 확인 완료(2026-10-21) 
- [x] 정적 백업 확인(로컬 API 실제 중지, 배포 주소 백업 모드, web-draft) + 시연 대본 고양시·배포 주소 기준 재작성(docs/demo_script.md), 배포 화면에서 대본 수치 확인
- [ ] 발표자 본인 리허설 1회(대본 소리 내어, 4분)
- [x] 사례 카드 요약 4건 — Claude 초안 반영(#40), 발표 전 사용자 검토
- [x] README·인계 문서에 배포 주소
- [ ] 발표자료 갱신(requests #35 목록) — 맨 마지막
- [x] 광주·전남 잘못된 '신규 설치' 이력 9,546건 삭제(2026-10-21 사용자 허락)
- [x] 마커 묶어 보이기(19번): 성능 문제 없어 넣지 않음, TOP 3 같은 이름 중복 제거(#43)
- [x] APP_MODE=dev 유지(#42)

