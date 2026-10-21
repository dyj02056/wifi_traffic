// contracts/golden_scores.json 전부 통과 필수 (plan.md §6.4, §13)
//
// [이 테스트가 확인하는 것]
//   브라우저용 채점 코드(src/lib/score.ts)가 백엔드 Python 채점과 똑같은 답을 내는지 확인합니다.
//   golden_scores.json(정답표)의 사례마다 computeScore를 돌려 오류 코드·등급·경고·점수(허용 오차 0.01)가 같은지 비교합니다.
//   it.each: 정답표의 사례 하나하나를 각각 별도의 테스트로 실행한다. "$id"는 테스트 이름으로 사례 id를 쓴다는 뜻.
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { computeScore } from "../src/lib/score";

interface GoldenCase {
  id: string;
  r: number[];
  weights: number[];
  selected: boolean[];
  expected_score: number | null;
  expected_grade: string | null;
  expected_error: string | null;
  expected_warnings: string[];
}

const golden = JSON.parse(readFileSync(path.resolve(__dirname, "../../contracts/golden_scores.json"), "utf8"));

describe(`golden_scores.json (${golden.generated_from}, ${golden.cases.length}건)`, () => {
  it.each(golden.cases as GoldenCase[])("$id", (c) => {
    const res = computeScore(c.r, c.weights, c.selected, golden.grades, golden.params);
    expect(res.error).toBe(c.expected_error);
    expect(res.grade).toBe(c.expected_grade);
    expect(res.warnings).toEqual(c.expected_warnings);
    if (c.expected_score == null) expect(res.score).toBeNull();
    else expect(Math.abs((res.score as number) - c.expected_score)).toBeLessThanOrEqual(golden.tolerance);
  });
});
