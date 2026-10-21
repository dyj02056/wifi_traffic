// 공용 채점 공식 (plan.md §6.3) — backend/src/wifisafe/scoring.py, web-draft/js/score.js와 같은 결과를 내야 한다.
// contracts/golden_scores.json으로 검증한다(tests/score.golden.test.ts). 가중치·파라미터 숫자는 rules.json에서 받는다.
//
// [이 파일이 하는 일]
//   사용자가 지도 화면에서 가중치 슬라이더를 움직이거나 위험요인을 끄면, 서버에 다시 묻지 않고
//   브라우저 안에서 바로 점수를 다시 계산합니다. 그래서 지도 색과 순위가 즉시 바뀝니다.
//
// [점수 공식]
//   점수 = 100 × (켜 둔 요인들의 '가중치 × 위험비율' 합) ÷ (켜 둔 요인들의 가중치 합)
//   위험비율(r)은 서버가 미리 계산해 보낸 0~1 사이 값입니다.

// 점수를 낼 수 없을 때의 오류 코드와 경고 코드 (백엔드와 같은 글자를 쓴다)
export const ERR_TOO_FEW_RULES = "TOO_FEW_RULES"; // 켜 둔 요인이 너무 적음
export const ERR_ZERO_WEIGHT = "ZERO_WEIGHT"; // 켜 둔 요인의 가중치 합이 0
export const WARN_LOW_MAXSUM = "LOW_MAXSUM"; // 가중치 합이 작아 근거가 빈약함

/** 등급 구간 하나. min 이상 max 미만이면 label 등급. 예) { min: 30, max: 60, label: "주의" } */
export interface GradeDef {
  min: number;
  max: number;
  label: string;
}

/** 채점 규칙 숫자. MIN_SELECTED_RULES: 최소로 켜야 하는 요인 수, LOW_MAXSUM_WARN: 경고를 띄울 가중치 합 기준 */
export interface ScoreParams {
  MIN_SELECTED_RULES: number;
  LOW_MAXSUM_WARN: number;
}

/** 채점 결과. 오류면 score·grade가 null이고 error에 코드가 들어간다. */
export interface ScoreResult {
  score: number | null;
  grade: string | null;
  error: typeof ERR_TOO_FEW_RULES | typeof ERR_ZERO_WEIGHT | null;
  warnings: string[];
}

/** round2(x) = floor(x*100 + 0.5 + 1e-9) / 100 — toFixed·Math.round 대신 이것만 쓴다.
 *  소수 둘째 자리 반올림. 1e-9(아주 작은 수)는 12.345가 12.34499…로 저장돼 내림되는 것을 막는다. */
export function round2(x: number): number {
  return Math.floor(x * 100 + 0.5 + 1e-9) / 100;
}

/** 점수가 들어가는 등급 구간을 찾아 등급 이름을 돌려준다. 예) 45 → "주의" */
export function gradeFor(score: number, grades: GradeDef[]): string {
  for (const g of grades) {
    if (g.min <= score && score < g.max) return g.label;
  }
  throw new Error(`등급 구간에 속하지 않는 점수: ${score}`);
}

/**
 * 점수 계산 본체.
 * @param r        R1~R8 위험비율(0~1)
 * @param weights  R1~R8 가중치(슬라이더 값)
 * @param selected R1~R8 켜짐(true)/꺼짐(false)
 * @param grades   등급 구간표 (rules.json)
 * @param params   채점 규칙 숫자 (rules.json)
 */
export function computeScore(
  r: number[], weights: number[], selected: boolean[], grades: GradeDef[], params: ScoreParams,
): ScoreResult {
  if (r.length !== weights.length || r.length !== selected.length) throw new Error("r, weights, selected 길이가 다름");
  // 켜 둔 요인의 순번만 모은다. 예) [true, false, true] → [0, 2]
  const idx = selected.flatMap((s, i) => (s ? [i] : []));
  if (idx.length < params.MIN_SELECTED_RULES) return { score: null, grade: null, error: ERR_TOO_FEW_RULES, warnings: [] };
  // 분모: 켜 둔 요인의 가중치 합
  const wsum = idx.reduce((a, i) => a + weights[i], 0);
  if (wsum <= 0) return { score: null, grade: null, error: ERR_ZERO_WEIGHT, warnings: [] };
  const warnings = wsum < params.LOW_MAXSUM_WARN ? [WARN_LOW_MAXSUM] : [];
  // 분자: 켜 둔 요인의 '가중치 × 위험비율' 합
  const acc = idx.reduce((a, i) => a + weights[i] * r[i], 0);
  const score = round2((100 * acc) / wsum);
  return { score, grade: gradeFor(score, grades), error: null, warnings };
}
