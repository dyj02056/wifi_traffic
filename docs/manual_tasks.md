# 사람이 직접 해야 하는 작업 체크리스트 (담당 A)

> 다운로드 페이지 주소는 2026-10-20에 열어서 확인했습니다. D2~D5는 "파일데이터는 로그인 없이 다운로드" 가능합니다.
> 받은 CSV는 **이름을 바꾸지 말고** 아래 폴더에 그대로 넣은 다음 `import_downloads.py`를 실행합니다.

## 1. 다운로드 → 폴더에 넣기

| # | 데이터 | 다운로드 페이지 | 넣을 폴더 | 필수 |
|---|---|---|---|---|
| D1 | 전국무료와이파이표준데이터 | https://www.data.go.kr/data/15013116/standard.do | `downloads\D1_전국무료와이파이\` | ★ 필수, 2~3일 간격 반복 |
| D2 | 서울특별시 구로구_공공와이파이 서비스 위치 정보 | https://www.data.go.kr/data/15147901/fileData.do | `downloads\D2_구로구와이파이\` | R1 검증 |
| D3 | 경찰청_연도별 사이버 범죄 통계 현황 | https://www.data.go.kr/data/15053887/fileData.do | `downloads\D3_경찰청사이버범죄\` | 배경 패널 |
| D4 | 한국인터넷진흥원_국내 민간 분야 기업 업종별 침해사고 신고 건수 | https://www.data.go.kr/data/15155733/fileData.do | `downloads\D4_KISA업종별침해사고\` | 배경 패널 |
| D5 | 한국인터넷진흥원_국내 민간 분야 침해사고 신고 건수 | https://www.data.go.kr/data/15140309/fileData.do | `downloads\D5_KISA민간침해사고\` | 선택 |

넣은 뒤 실행(저장소 루트, PowerShell):

    .\backend\.venv\Scripts\python.exe backend\pipeline\import_downloads.py

- D1 → `backend\data\raw\snapshots\YYYY-MM-DD.csv`로 등록됩니다(수집일 = 파일 받은 날짜).
- D2~D5 → `backend\data\external\`에 복사되고, 수집일은 `.meta.json`에 기록됩니다.
- **D1은 마감 전까지 3~4회** 받습니다. 받을 때마다 새 파일을 D1 폴더에 추가하고 위 명령을 다시 실행합니다(이미 등록된 날짜는 건너뜁니다).

## 2. 라벨 확정 (리드와 함께, D1 등록·census 후)

- [ ] `backend\data\interim\ssid_census.csv`를 보고 **`backend\config\ssid_labels.csv`** 작성
      (`ssid,label,evidence,reviewer,reviewed_at,status` / label = open·secure·unknown / 검토가 끝나면 status = confirmed)
      → 행 기준 커버리지 95% 이상 (M2). 후보 라벨은 `ai_label_assist.py`로 뽑을 수 있지만, 확정은 사람이 합니다.
- [ ] `backend\data\interim\facility_census.csv`를 보고 **`backend\config\facility_map.csv`** 작성 (`facility_type,ratio,reason,status`, ratio는 0/0.25/0.5/1.0)
- [ ] `backend\data\interim\place_detail_census.csv`를 보고 **`backend\config\keywords.yaml`**의 실외 키워드 확정 (r3_status: confirmed)
- [ ] 구로구 CSV 컬럼을 보고 **`backend\config\guro_validation.yaml`**에 컬럼명과 `wifi접속환경` 값 → open/secure 매핑 작성

## 3. 직접 작성

- [ ] **`backend\data\cases.yaml`**: 사례 카드. 기사를 직접 읽고 요약을 쓰고, 출처명·URL·게재일·확인일을 적습니다. 출처가 없으면 export가 멈춥니다.
- [ ] `backend\.env` (`backend\.env.example`을 복사): `ANTHROPIC_API_KEY`(넣지 않음 — 설명은 근거값 기반 자동 설명으로 운영, docs/requests.md #36)

## 4. 소통

- [ ] `contracts\` 폴더와 `contracts\README.md`를 담당 B에게 전달
- [ ] `docs\requests.md` #1(지도 타일), #6(저합계 경고 기준), #8(R8 결측 처리)을 리드에게 확인받기
- [ ] 시연 지역 확정(현재 구로구 `11-guro` 가정), 해커톤 마감일 확정
