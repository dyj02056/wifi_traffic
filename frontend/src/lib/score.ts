// 공용 채점 공식 (plan.md §6.3) — backend/src/wifisafe/scoring.py, web-draft/js/score.js와 같은 결과를 내야 한다.
// contracts/golden_scores.json으로 검증한다(tests/score.golden.test.ts). 가중치·파라미터 숫자는 rules.json에서 받는다.

export const ERR_TOO_FEW_RULES = "TOO_FEW_RULES";
export const ERR_ZERO_WEIGHT = "ZERO_WEIGHT";
export const WARN_LOW_MAXSUM = "LOW_MAXSUM";

export interface GradeDef {
  min: number;
  max: number;
  label: string;
}

export interface ScoreParams {
  MIN_SELECTED_RULES: number;
  LOW_MAXSUM_WARN: number;
}

export interface ScoreResult {
  score: number | null;
  grade: string | null;
  error: typeof ERR_TOO_FEW_RULES | typeof ERR_ZERO_WEIGHT | null;
  warnings: string[];
}

/** round2(x) = floor(x*100 + 0.5 + 1e-9) / 100 — toFixed·Math.round 대신 이것만 쓴다. */
export function round2(x: number): number {
  return Math.floor(x * 100 + 0.5 + 1e-9) / 100;
}

export function gradeFor(score: number, grades: GradeDef[]): string {
  for (const g of grades) {
    if (g.min <= score && score < g.max) return g.label;
  }
  throw new Error(`등급 구간에 속하지 않는 점수: ${score}`);
}

export function computeScore(
  r: number[], weights: number[], selected: boolean[], grades: GradeDef[], params: ScoreParams,
): ScoreResult {
  if (r.length !== weights.length || r.length !== selected.length) throw new Error("r, weights, selected 길이가 다름");
  const idx = selected.flatMap((s, i) => (s ? [i] : []));
  if (idx.length < params.MIN_SELECTED_RULES) return { score: null, grade: null, error: ERR_TOO_FEW_RULES, warnings: [] };
  const wsum = idx.reduce((a, i) => a + weights[i], 0);
  if (wsum <= 0) return { score: null, grade: null, error: ERR_ZERO_WEIGHT, warnings: [] };
  const warnings = wsum < params.LOW_MAXSUM_WARN ? [WARN_LOW_MAXSUM] : [];
  const acc = idx.reduce((a, i) => a + weights[i] * r[i], 0);
  const score = round2((100 * acc) / wsum);
  return { score, grade: gradeFor(score, grades), error: null, warnings };
}
