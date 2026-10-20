// contracts/golden_scores.json 전부 통과 필수 (plan.md §6.4, §13)
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
