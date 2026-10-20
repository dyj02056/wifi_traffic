"use client";
// 채점 기준 — rules.json으로 표 자동 생성 (plan.md §9.3, 발표 채점표 캡처용)
import { DocShell } from "@/components/DocShell";
import { useRules } from "@/lib/queries";

export default function RulesPage() {
  const { data: rules, error } = useRules();
  return (
    <DocShell>
      <h1>채점 기준표</h1>
      <p>점수가 높을수록 위험요인이 많다는 뜻입니다. 이 표는 rules.json에서 자동으로 만들어집니다.</p>
      {error && <div className="notice error">채점 기준을 불러오지 못했습니다.</div>}
      {rules && (
        <>
          <table>
            <thead><tr><th>ID</th><th>위험요인</th><th>만점</th><th>근거 필드</th><th>가정</th><th>1줄 설명</th></tr></thead>
            <tbody>
              {rules.rules.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td><td>{r.name}</td><td>{r.max_points}</td><td>{r.source_fields.join(", ")}</td>
                  <td>{r.is_assumption ? <span className="badge assumption">가정</span> : "—"}</td><td>{r.one_liner}</td>
                </tr>
              ))}
              <tr><th colSpan={2}>합계</th><th>{rules.rules.reduce((a, r) => a + r.max_points, 0)}</th><td colSpan={3} /></tr>
            </tbody>
          </table>
          <section>
            <h2>등급 기준</h2>
            <table>
              <thead><tr><th>등급</th><th>점수 구간</th><th>색</th></tr></thead>
              <tbody>
                {rules.grades.map((g) => (
                  <tr key={g.label}>
                    <td>{g.emoji} {g.label}</td><td>{g.min} 이상 {g.max > 100 ? "100 이하" : `${g.max} 미만`}</td>
                    <td><span className="dot" style={{ background: g.color }} />{g.color}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section>
            <h2>계산 방법</h2>
            <ul>
              {Object.values(rules.formula).map((f) => <li key={f}><code>{f}</code></li>)}
              <li>선택 규칙이 {rules.params.MIN_SELECTED_RULES}개 미만이면 계산하지 않습니다. 선택한 가중치 합이 {rules.params.LOW_MAXSUM_WARN} 미만이면 경고합니다.</li>
            </ul>
          </section>
        </>
      )}
    </DocShell>
  );
}
