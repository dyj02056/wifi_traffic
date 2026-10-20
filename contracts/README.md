# contracts/ — 담당 A ↔ 담당 B 경계선 (v1.0.0)

> ※ 이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.

소유: 담당 A. 버전: [`VERSION`](VERSION). 필드 추가 = minor, 필드 삭제·의미 변경 = major + 상대 담당 확인 후 반영.

## 구성

| 경로 | 내용 |
|---|---|
| `schemas/*.schema.json` | JSON Schema(draft 2020-12) 10종 + `_common` 공용 정의 |
| `mock/` | 가짜 번들(가상 지역 `99-gasang`, 지점 40개, `meta.is_mock=true`) — **발표 화면 사용 금지** |
| `golden_scores.json` | 채점 공식 골든 케이스(51건). 세 구현(Python·초안 JS·Next.js TS) 모두 통과 필수 |

## 파일 ↔ API 대응 (정적 번들 base 경로 뒤에 붙인다)

| 정적 파일 | API | 스키마 |
|---|---|---|
| `meta.json` | `GET /api/meta` | meta |
| `rules.json` | `GET /api/rules` | rules |
| `regions.json` | `GET /api/regions` | regions |
| `points/{region_id}.json` | `GET /api/regions/{region_id}/points` | points |
| `detail/{region_id}.json` (key → 상세 맵) | `GET /api/points/{key}` (단건) | detail |
| `key_index.json` | (공개 엔드포인트 없음) | key_index |
| `changes/{region_id}.json` | `GET /api/regions/{region_id}/changes` | changes |
| `sensitivity/{region_id}.json` | `GET /api/regions/{region_id}/sensitivity` | sensitivity |
| `background.json` | `GET /api/background` | background |
| `cases.json` | `GET /api/cases` | cases |
| — | `POST /api/points/{key}/explain` | (api/models.py ExplainResponse) |

base 경로 예: 정적 `/data`, mock `/mock`, API `http://localhost:8000/api`.
API 모드에서 상세는 지점별 단건(`/points/{key}`)이고, 정적 모드에서는 `detail/{region_id}.json`을 받아 key로 꺼낸다.

## 채점 공식 (§6.3) — 구현 시 꼭 지킬 것

```
S = 선택된 규칙, w_i = 현재 슬라이더 가중치, r_i = points[].r[i] (R1~R8 순서 고정)
|S| < MIN_SELECTED_RULES        → error "TOO_FEW_RULES" (먼저 검사), score/grade = null
Σ_{i∈S} w_i ≤ 0                 → error "ZERO_WEIGHT", score/grade = null
score = round2(100 × Σ w_i r_i / Σ w_i)
round2(x) = floor(x*100 + 0.5 + 1e-9) / 100        ← Math.round·toFixed 쓰지 말 것
grade = grades에서 min ≤ score < max (반올림된 score로)
Σ_{i∈S} w_i < LOW_MAXSUM_WARN   → warnings ["LOW_MAXSUM"] (계산은 함)
```

숫자(가중치·임계값·색)는 코드에 쓰지 말고 `rules.json`에서 읽는다. 기본 가중치 = `rules[].max_points`, 슬라이더 범위 0 ~ 2×max_points.

## 프론트엔드 표시 규칙

- `meta.disclaimer`를 모든 화면 상단에 고정 표시
- `meta.is_mock=true` → "샘플 데이터" 배지, `meta.r1_confirmed=false` → "임시(무효)" 워터마크
- `rules[].is_assumption=true` → "가정" 배지
- `background.included_in_score=false` → "이 통계는 지점 점수에 반영하지 않습니다" 고정
- `cases.label` 그대로 표시. 출처(`source`)가 없는 항목은 스키마상 존재할 수 없음
- `points[].flags` 값: `R1_ssid_missing R1_unlabeled R1_unknown R2_unmapped R4_missing R4_year_only R5_boundary R7_invalid_tel R8_missing`
  (flag는 표시용 문자열이며 앞으로 추가될 수 있다. 모르는 flag는 원문 그대로 보여주면 된다)
- 기본 시연 지역은 `regions.json`의 `default_region_id`를 읽는다. `11-guro`를 코드에 고정하지 말 것(시연 지역 변경 검토 중)

## golden_scores.json 형식

```json
{"tolerance": 0.01, "grades": [...], "params": {"MIN_SELECTED_RULES": 2, "LOW_MAXSUM_WARN": 30},
 "cases": [{"id": "...", "r": [...8], "weights": [...8], "selected": [...8],
            "expected_score": 75.25 | null, "expected_grade": "높음" | null,
            "expected_error": null | "TOO_FEW_RULES" | "ZERO_WEIGHT", "expected_warnings": [] | ["LOW_MAXSUM"]}]}
```

기대값은 사람이 쓰지 않는다. `backend/pipeline/make_mock.py`(mock 기반)와 `export_bundle.py`(실데이터 샘플 포함)가 생성한다.
