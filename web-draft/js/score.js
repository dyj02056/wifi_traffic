// 공용 채점 공식 (plan.md §6.3) — backend/src/wifisafe/scoring.py와 같은 결과를 내야 한다.
// contracts/golden_scores.json으로 검증한다(tests/score.test.html, tests/score.test.mjs).
// 가중치·파라미터 숫자는 여기 쓰지 않는다. 모두 rules.json에서 받는다.

export const ERR_TOO_FEW_RULES = "TOO_FEW_RULES";
export const ERR_ZERO_WEIGHT = "ZERO_WEIGHT";
export const WARN_LOW_MAXSUM = "LOW_MAXSUM";

// round2(x) = floor(x*100 + 0.5 + 1e-9) / 100  — toFixed·Math.round 대신 이것만 쓴다.
export function round2(x) {
  return Math.floor(x * 100 + 0.5 + 1e-9) / 100;
}

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
  const idx = [];
  selected.forEach((s, i) => { if (s) idx.push(i); });
  if (idx.length < params.MIN_SELECTED_RULES) return { score: null, grade: null, error: ERR_TOO_FEW_RULES, warnings: [] };
  let wsum = 0;
  for (const i of idx) wsum += weights[i];
  if (wsum <= 0) return { score: null, grade: null, error: ERR_ZERO_WEIGHT, warnings: [] };
  const warnings = wsum < params.LOW_MAXSUM_WARN ? [WARN_LOW_MAXSUM] : [];
  let acc = 0;
  for (const i of idx) acc += weights[i] * r[i];
  const score = round2((100 * acc) / wsum);
  return { score, grade: gradeFor(score, grades), error: null, warnings };
}
