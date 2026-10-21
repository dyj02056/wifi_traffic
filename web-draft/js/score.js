// 공용 채점 공식 (plan.md §6.3) — backend/src/wifisafe/scoring.py와 같은 결과를 내야 한다.
// contracts/golden_scores.json으로 검증한다(tests/score.test.html, tests/score.test.mjs).
// 가중치·파라미터 숫자는 여기 쓰지 않는다. 모두 rules.json에서 받는다.
//
// [이 파일이 하는 일]
//   정적 초안(web-draft) 화면에서 슬라이더를 움직이면 브라우저 안에서 점수를 다시 계산한다.
//   점수 = 100 × (켜 둔 요인들의 '가중치 × 위험비율' 합) ÷ (켜 둔 요인들의 가중치 합)

// 점수를 낼 수 없을 때의 오류 코드와 경고 코드 (백엔드와 같은 글자)
export const ERR_TOO_FEW_RULES = "TOO_FEW_RULES"; // 켜 둔 요인이 너무 적음
export const ERR_ZERO_WEIGHT = "ZERO_WEIGHT"; // 켜 둔 요인의 가중치 합이 0
export const WARN_LOW_MAXSUM = "LOW_MAXSUM"; // 가중치 합이 작아 근거가 빈약함

// round2(x) = floor(x*100 + 0.5 + 1e-9) / 100  — toFixed·Math.round 대신 이것만 쓴다.
// 소수 둘째 자리 반올림. 1e-9는 12.345가 12.34499…로 저장돼 내림되는 것을 막는 아주 작은 보정값.
export function round2(x) {
  return Math.floor(x * 100 + 0.5 + 1e-9) / 100;
}

// 점수가 들어가는 등급 구간(min 이상 max 미만)을 찾아 등급 이름을 돌려준다. 예) 45 → "주의"
export function gradeFor(score, grades) {
  for (const g of grades) {
    if (g.min <= score && score < g.max) return g.label;
  }
  throw new Error(`등급 구간에 속하지 않는 점수: ${score}`);
}

/**
 * @param {number[]} r        R1~R8 위험비율(0~1)
 * @param {number[]} weights  R1~R8 가중치(슬라이더 값)
 * @param {boolean[]} selected R1~R8 선택 여부
 * @param {{min:number,max:number,label:string}[]} grades rules.json grades
 * @param {{MIN_SELECTED_RULES:number, LOW_MAXSUM_WARN:number}} params rules.json params
 * @returns {{score:number|null, grade:string|null, error:string|null, warnings:string[]}}
 */
export function computeScore(r, weights, selected, grades, params) {
  if (r.length !== weights.length || r.length !== selected.length) throw new Error("r, weights, selected 길이가 다름");
  // 켜 둔 요인의 순번만 모은다
  const idx = [];
  selected.forEach((s, i) => { if (s) idx.push(i); });
  if (idx.length < params.MIN_SELECTED_RULES) return { score: null, grade: null, error: ERR_TOO_FEW_RULES, warnings: [] };
  // 분모: 켜 둔 요인의 가중치 합
  let wsum = 0;
  for (const i of idx) wsum += weights[i];
  if (wsum <= 0) return { score: null, grade: null, error: ERR_ZERO_WEIGHT, warnings: [] };
  const warnings = wsum < params.LOW_MAXSUM_WARN ? [WARN_LOW_MAXSUM] : [];
  // 분자: 켜 둔 요인의 '가중치 × 위험비율' 합
  let acc = 0;
  for (const i of idx) acc += weights[i] * r[i];
  const score = round2((100 * acc) / wsum);
  return { score, grade: gradeFor(score, grades), error: null, warnings };
}
