// 터미널용 골든 테스트: node web-draft/tests/score.test.mjs
// contracts/golden_scores.json을 직접 읽어 web-draft/js/score.js를 검증한다(브라우저 score.test.html과 같은 판정).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { computeScore } from "../js/score.js";

const goldenPath = fileURLToPath(new URL("../../contracts/golden_scores.json", import.meta.url));
const golden = JSON.parse(readFileSync(goldenPath, "utf-8"));
let fails = 0;
for (const c of golden.cases) {
  const out = computeScore(c.r, c.weights, c.selected, golden.grades, golden.params);
  const scoreOk = c.expected_score === null ? out.score === null : Math.abs(out.score - c.expected_score) <= golden.tolerance;
  const ok = scoreOk && out.grade === c.expected_grade && out.error === c.expected_error
    && JSON.stringify(out.warnings) === JSON.stringify(c.expected_warnings);
  if (!ok) {
    fails += 1;
    console.log(`FAIL ${c.id}: expected ${JSON.stringify([c.expected_score, c.expected_grade, c.expected_error])} got ${JSON.stringify([out.score, out.grade, out.error])}`);
  }
}
console.log(`score.js golden: ${golden.cases.length - fails}/${golden.cases.length} passed (generated_from=${golden.generated_from})`);
process.exit(fails ? 1 : 0);
