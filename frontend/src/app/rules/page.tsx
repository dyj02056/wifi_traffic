"use client";
// 채점 기준 — rules.json으로 자동 생성 (plan.md §9.3, 발표 "채점이 투명하다" 화면, requests #45)
// 머리 요약 → ① 100점 구성 막대 → ② 위험요인 카드 → ③ 신호등 등급 눈금 → ④ 수식 + 실제 지점 예시 계산
//
// [이 파일이 하는 일]
//   "/rules" 화면: 점수가 어떻게 계산되는지 누구나 확인할 수 있게 보여 줍니다(채점의 투명성).
//   내용은 모두 rules.json(백엔드 config/rules.py에서 만들어짐)에서 자동으로 채워지므로,
//   백엔드에서 가중치를 바꾸면 이 화면도 저절로 바뀝니다. 수식은 Formula(KaTeX)로 그립니다.
import type { CSSProperties } from "react";
import { DocShell } from "@/components/DocShell";
import { Formula } from "@/components/Formula";
import { fmt } from "@/components/format";
import { useDetail, usePoints, useRegions, useRules } from "@/lib/queries";
import type { RulesDoc } from "@/lib/types";

// 규칙 색: 배점이 큰 규칙일수록 진한 파랑 (등급 색과 겹치지 않게 파랑 계열만)
const RULE_SHADES = ["#1e3a8a", "#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe", "#dbeafe"];
const LIGHT = new Set(["#93c5fd", "#bfdbfe", "#dbeafe"]);   // 바탕이 연해서 글자를 진한 색으로 써야 하는 색
// 요인 id → 색: 배점 큰 순으로 줄 세운 순번의 색을 고른다
function shadeOf(rules: RulesDoc, id: string) {
  const order = [...rules.rules].sort((a, b) => b.max_points - a.max_points || (a.id < b.id ? -1 : 1)).map((r): string => r.id);
  return RULE_SHADES[order.indexOf(id)] ?? RULE_SHADES[RULE_SHADES.length - 1];
}
// chip: 색 배지 스타일, round2: 백엔드·score.ts와 같은 소수 둘째 자리 반올림
const chip = (c: string): CSSProperties => ({ background: c, color: LIGHT.has(c) ? "#1e3a8a" : "#fff" });
const round2 = (x: number) => Math.floor(x * 100 + 0.5 + 1e-9) / 100;

/** ④ 기본 지역에서 기본 점수가 가장 높은 지점으로 실제 계산 과정을 보여 준다 */
function Example({ rules }: { rules: RulesDoc }) {
  const regions = useRegions();
  const rid = regions.data?.default_region_id ?? null;
  const region = regions.data?.regions.find((r) => r.region_id === rid);
  const pts = usePoints(rid).data?.points ?? [];
  const top = pts.reduce<(typeof pts)[number] | null>(
    (a, p) => (!a || p.score > a.score || (p.score === a.score && p.key < a.key) ? p : a), null);
  const d = useDetail(top?.key ?? null).data;
  if (!d || !region) return <p className="field">예시 지점을 불러오는 중…</p>;
  // 공식의 분모(가중치 합)와 분자(가중치 × 비율의 합)를 직접 계산해 보여 준다
  const wsum = d.breakdown.reduce((a, b) => a + b.max_points, 0);
  const num = d.breakdown.reduce((a, b) => a + b.max_points * b.ratio, 0);
  const g = rules.grades.find((x) => x.label === d.grade);
  return (
    <div className="example">
      <p className="example-title">
        실제 지점 예시 · <b>{d.name}</b> <span className="field">({region.sido} {region.sigungu}, 기본 가중치에서 가장 높은 점수)</span>
      </p>
      <table className="example-table">
        <thead><tr><th>위험요인</th><th>근거</th><th>가중치 w</th><th>비율 r</th><th>w × r</th></tr></thead>
        <tbody>
          {d.breakdown.map((b) => (
            <tr key={b.id} className={b.ratio ? "" : "zero"}>
              <td><span className="rule-id" style={chip(shadeOf(rules, b.id))}>{b.id}</span> {b.name}</td>
              <td className="reason">{b.reason}</td>
              <td>{b.max_points}</td><td>{b.ratio.toLocaleString("ko-KR", { maximumFractionDigits: 4 })}</td><td><b>{fmt(round2(b.max_points * b.ratio))}</b></td>
            </tr>
          ))}
        </tbody>
      </table>
      <Formula block tex={String.raw`\text{score} = \operatorname{round}_2\!\left(100 \times \frac{${round2(num)}}{${wsum}}\right) = ${fmt(d.score)}`} />
      <p className="example-result" style={{ "--c": g?.color ?? "var(--grade-none)" } as CSSProperties}>
        → <b>{fmt(d.score)}점 · {g?.label}</b> <span className="field">지도에서 이 지점을 누르면 같은 값이 보입니다.</span>
      </p>
    </div>
  );
}

// 페이지 본체: 요약 숫자 → ①~④ 구역
export default function RulesPage() {
  const { data: rules, error } = useRules();
  const total = rules?.rules.reduce((a, r) => a + r.max_points, 0) ?? 0;
  return (
    <DocShell>
      <header className="rules-hero">
        <h1>채점 기준</h1>
        <p>공공데이터 근거값으로 위험요인 {rules?.rules.length ?? 8}가지를 채점해 0~100점으로 합칩니다.
          점수가 높을수록 위험요인이 많다는 뜻이며, 이 화면은 rules.json에서 자동으로 만들어집니다.</p>
        {rules && (
          <div className="kpis">
            <div><b>{rules.rules.length}가지</b><span>위험요인</span></div>
            <div><b>{total}점</b><span>기본 만점 합</span></div>
            <div><b>{rules.grades.length}단계</b><span>{rules.grades.map((g) => g.label).join(" · ")}</span></div>
          </div>
        )}
      </header>
      {error && <div className="notice error">채점 기준을 불러오지 못했습니다.</div>}
      {rules && (
        <>
          <section>
            <h2><span className="step">1</span> 100점은 이렇게 나뉩니다</h2>
            <div className="points-stack" role="img" aria-label={rules.rules.map((r) => `${r.id} ${r.max_points}점`).join(", ")}>
              {rules.rules.map((r) => (
                <div key={r.id} style={{ ...chip(shadeOf(rules, r.id)), width: `${(100 * r.max_points) / total}%` }}
                  title={`${r.id} ${r.name} ${r.max_points}점`}>
                  {r.id}{r.max_points >= 10 && <small>{r.max_points}</small>}
                </div>
              ))}
            </div>
            <p className="field">지도 화면의 슬라이더로 각 가중치를 0~2배까지 바꿔 볼 수 있습니다. 위 막대는 기본값입니다.</p>
          </section>

          <section>
            <h2><span className="step">2</span> 위험요인 {rules.rules.length}가지</h2>
            <div className="rule-cards">
              {rules.rules.map((r) => {
                const c = shadeOf(rules, r.id);
                return (
                  <article key={r.id} className="rule-card" style={{ "--rc": c } as CSSProperties}>
                    <div className="rc-head">
                      <span className="rule-id" style={chip(c)}>{r.id}</span>
                      <span className="rc-points">{r.max_points}<small>점</small></span>
                    </div>
                    <h3>{r.name}{r.is_assumption && <span className="badge assumption" title="가정 기반 규칙">가정</span>}</h3>
                    <p>{r.one_liner}</p>
                    <div className="rc-fields">{r.source_fields.map((f) => <code key={f}>{f}</code>)}</div>
                  </article>
                );
              })}
            </div>
            <p className="field"><span className="badge assumption">가정</span> 표시는 공개 데이터만으로 확인할 수 없어 합리적인 가정을 둔 항목입니다.</p>
          </section>

          <section>
            <h2><span className="step">3</span> 등급 — 지도 색과 같은 신호등</h2>
            <div className="grade-scale">
              {rules.grades.map((g) => (
                <div key={g.label} style={{ width: `${Math.min(g.max, 100) - g.min}%`, background: g.color }}>
                  {g.label}<small>{g.min} 이상 {g.max > 100 ? "100 이하" : `${g.max} 미만`}</small>
                </div>
              ))}
            </div>
            <div className="grade-ticks">
              {[0, ...rules.grades.slice(0, -1).map((g) => g.max), 100].map((t) => (
                <span key={t} style={{ left: `${t}%` }}>{t}</span>
              ))}
            </div>
          </section>

          <section className="formula">
            <h2><span className="step">4</span> 계산 방법</h2>
            <p>선택한 위험요인 <Formula tex="S" />의 비율 <Formula tex={String.raw`r_i \in [0, 1]`} />에 가중치 <Formula tex="w_i" />(기본값 = 만점)를 곱해 더한 뒤,
              가중치 합으로 나눠 0~100점으로 맞춥니다.</p>
            <Formula block tex={String.raw`\text{score} \;=\; \operatorname{round}_2\!\left(100 \times \frac{\displaystyle\sum_{i \in S} w_i\, r_i}{\displaystyle\sum_{i \in S} w_i}\right)`} />
            <Example rules={rules} />
            <h3>반올림</h3>
            <p>Python <code>round()</code>(은행가 반올림)와 JavaScript <code>toFixed</code>는 결과가 달라서 쓰지 않습니다. 두 언어 모두 아래 식을 씁니다.</p>
            <Formula block tex={String.raw`\operatorname{round}_2(x) \;=\; \frac{\left\lfloor\, 100x + 0.5 + 10^{-9} \,\right\rfloor}{100}`} />
            <h3>등급</h3>
            <p>반올림한 점수가 들어가는 구간으로 정합니다.</p>
            <Formula block tex={String.raw`\text{grade} = g \iff \min_g \le \text{score} < \max_g`} />
            <h3>계산하지 않거나 경고하는 경우</h3>
            <ul className="formula-cases">
              <li><Formula tex={String.raw`|S| < ${rules.params.MIN_SELECTED_RULES}`} /> → 계산하지 않음 (위험요인을 2개 이상 선택해야 함)</li>
              <li><Formula tex={String.raw`\sum_{i \in S} w_i \le 0`} /> → 계산하지 않음 (가중치 합이 0)</li>
              <li><Formula tex={String.raw`\sum_{i \in S} w_i < ${rules.params.LOW_MAXSUM_WARN}`} /> → 계산은 하되 경고 (점수가 소수 요인에 크게 좌우됨)</li>
            </ul>
          </section>
        </>
      )}
    </DocShell>
  );
}
