# frontend — Next.js 앱 (공공와이파이 안전 지도)

> ※ 이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.

설계: [plan.md §9](../plan.md), 인계 문서: [docs/handoff_B.md](../docs/handoff_B.md), 데이터 계약: [contracts/](../contracts/README.md) (1.1.0)

```bash
npm install
cp .env.local.example .env.local   # API 주소, 카카오맵 키, (선택) 구글·네이버 클라이언트 ID
npm run gen:types                  # contracts/schemas → src/lib/types.ts (스키마 바뀌면)
npm test                           # contracts/golden_scores.json 51건
npm run dev                        # http://localhost:3000
```

- 데이터: `NEXT_PUBLIC_API_BASE`(우리 API) 우선 → 응답이 없으면 `public/data`(정적 번들, `bash ../scripts/sync_bundle.sh`)로 자동 전환하고 "정적 백업 데이터" 배지를 띄운다. 한 번 실패하면 5분간은 바로 정적 번들을 쓴다.
- 지도: 카카오맵(`NEXT_PUBLIC_KAKAO_JS_KEY`, 카카오 개발자 콘솔 [플랫폼 > Web]에 접속 주소 등록). 키가 없으면 지도 자리에 안내만 나오고 나머지는 동작한다.
- 로그인: 구글·네이버 토큰을 API가 검증하고 Neon 회원으로 저장. 로컬 주소에서만 "개발용 로그인"이 보인다(API·DB가 없으면 이 브라우저에만 저장).

| 경로 | 화면 |
|---|---|
| `/` | 인트로·로그인, 처음 로그인하면 사는 지역 선택 |
| `/map` | 지역 선택(첫 지역: `?region` → 회원 지역 → 기본 지역), 내 위치, 가중치 슬라이더, 등급 필터, 변경 레이어, 순위표, 지점 상세, 지역별 "임시(무효)"/"SSID 정보 없음" 표시 |
| `/rules` `/sensitivity` `/context` `/about` | 채점 기준표, 민감도 분석, 배경 통계·사례 카드, 데이터와 한계 |

이 버전의 Next.js(16)는 이전과 다른 점이 있다 — 코드를 고치기 전에 `node_modules/next/dist/docs/`를 확인한다(AGENTS.md).
