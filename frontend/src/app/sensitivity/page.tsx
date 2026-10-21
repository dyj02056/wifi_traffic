"use client";
// 민감도 분석 (requests #46) — 기준 하나의 가중치를 바꾸면 결과가 얼마나 흔들리는지.
// A 토네이도(8개 기준 × 끄기/2배) → 고른 경우의 숫자 카드 + B 등급 흐름도 → 더 보기(C 점수 산점도, D 기울기, 상위 표).
// 모든 값은 지도와 같은 채점 함수(lib/score.ts computeScore, 골든 테스트 통과)로 브라우저에서 계산한다.
// 순위 대신 점수·등급으로 보여 준다: 같은 점수 지점이 많아 순위는 작은 변화에도 크게 출렁이기 때문(이전 순위 산점도의 착시).
import { Suspense, useMemo, useState, type CSSProperties } from "react";
import { useSearchParams } from "next/navigation";
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { DocShell } from "@/components/DocShell";
import { usePlayOnView } from "@/lib/usePlayOnView";
import { fmt } from "@/components/format";
import { usePoints, useRegions, useRules } from "@/lib/queries";
import { computeScore } from "@/lib/score";
import type { RulesDoc } from "@/lib/types";

const TOP_N = 20;
const MULTS = [0, 0.5, 1.5, 2] as const;
const MULT_LABEL: Record<number, string> = { 0: "끄기 (×0)", 0.5: "절반 (×0.5)", 1.5: "1.5배", 2: "2배" };

interface Pt { key: string; name: string; r: number[] }
interface Scenario { rule: number; mult: number }
interface Outcome {
  scores: Map<string, { score: number; grade: string }>;
  moved: number; topKeep: number; meanAbs: number;
  flows: number[][];                // flows[i][j] = A 등급 i → B 등급 j 지점 수
}

function scoreAll(pts: Pt[], weights: number[], rules: RulesDoc) {
  const sel = weights.map(() => true);
  const m = new Map<string, { score: number; grade: string }>();
  for (const p of pts) {
    const s = computeScore(p.r, weights, sel, rules.grades, rules.params as never);
    if (s.score != null && s.grade) m.set(p.key, { score: s.score, grade: s.grade });
  }
  return m;
}
const topKeys = (m: Map<string, { score: number }>, n: number) =>
  new Set([...m].sort((a, b) => b[1].score - a[1].score || (a[0] < b[0] ? -1 : 1)).slice(0, n).map(([k]) => k));

function outcome(base: Map<string, { score: number; grade: string }>, pts: Pt[], rules: RulesDoc, sc: Scenario): Outcome {
  const w = rules.rules.map((r, i) => (i === sc.rule ? r.max_points * sc.mult : r.max_points));
  const scores = scoreAll(pts, w, rules);
  const gi = new Map<string, number>(rules.grades.map((g, i) => [g.label, i]));
  const flows = rules.grades.map(() => rules.grades.map(() => 0));
  let moved = 0, abs = 0;
  for (const [k, a] of base) {
    const b = scores.get(k);
    if (!b) continue;
    flows[gi.get(a.grade)!][gi.get(b.grade)!] += 1;
    if (a.grade !== b.grade) moved += 1;
    abs += Math.abs(b.score - a.score);
  }
  const ta = topKeys(base, TOP_N), tb = topKeys(scores, TOP_N);
  return { scores, moved, topKeep: [...ta].filter((k) => tb.has(k)).length, meanAbs: base.size ? abs / base.size : 0, flows };
}

function verdict(pct: number) {
  if (pct < 10) return { text: "결과가 안정적", cls: "ok" };
  if (pct < 30) return { text: "일부 지점이 영향을 받음", cls: "mid" };
  return { text: "결과가 크게 달라짐", cls: "big" };
}

/** B 등급 흐름도: 왼쪽 기본 등급 → 오른쪽 바뀐 기준의 등급, 굵기 = 지점 수 */
function GradeFlow({ flows, grades, leftLabel, rightLabel }: {
  flows: number[][]; grades: RulesDoc["grades"]; leftLabel: string; rightLabel: string;
}) {
  const W = 680, H = 260, NW = 92, GAP = 14, top = 28;
  const total = flows.flat().reduce((a, b) => a + b, 0) || 1;
  const scale = (H - top - GAP * (grades.length - 1)) / total;
  const left = grades.map((_, i) => flows[i].reduce((a, b) => a + b, 0));
  const right = grades.map((_, j) => flows.reduce((a, row) => a + row[j], 0));
  const ys = (sizes: number[]) => sizes.reduce<number[]>((acc, s, i) => [...acc, i ? acc[i - 1] + sizes[i - 1] * scale + GAP : top], []);
  const ly = ys(left), ry = ys(right);
  const lOff = [...ly], rOff = [...ry];
  const paths: { d: string; color: string; moved: boolean; n: number; mid: [number, number] }[] = [];
  grades.forEach((_, i) => grades.forEach((__, j) => {
    const n = flows[i][j];
    if (!n) return;
    const h = n * scale, x1 = NW, x2 = W - NW, y1 = lOff[i], y2 = rOff[j], cx = (x1 + x2) / 2;
    lOff[i] += h; rOff[j] += h;
    paths.push({ d: `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2} L${x2},${y2 + h} C${cx},${y2 + h} ${cx},${y1 + h} ${x1},${y1 + h} Z`,
      color: grades[j].color, moved: i !== j, n, mid: [cx, (y1 + y2 + h) / 2] });
  }));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="grade-flow" role="img"
      aria-label={paths.map((p) => `${p.n}곳`).join(", ")}>
      <text x={NW / 2} y={16} textAnchor="middle" className="gf-head">{leftLabel}</text>
      <text x={W - NW / 2} y={16} textAnchor="middle" className="gf-head">{rightLabel}</text>
      {paths.map((p, k) => <path key={k} d={p.d} fill={p.color} opacity={p.moved ? 0.75 : 0.22} />)}
      {grades.map((g, i) => left[i] > 0 && (
        <g key={`l${i}`}><rect x={0} y={ly[i]} width={NW} height={Math.max(left[i] * scale, 2)} rx={4} fill={g.color} />
          <text x={NW / 2} y={ly[i] + (left[i] * scale) / 2 + 4} textAnchor="middle" className="gf-node">{g.label} {left[i]}</text></g>
      ))}
      {grades.map((g, j) => right[j] > 0 && (
        <g key={`r${j}`}><rect x={W - NW} y={ry[j]} width={NW} height={Math.max(right[j] * scale, 2)} rx={4} fill={g.color} />
          <text x={W - NW / 2} y={ry[j] + (right[j] * scale) / 2 + 4} textAnchor="middle" className="gf-node">{g.label} {right[j]}</text></g>
      ))}
      {paths.filter((p) => p.moved).map((p, k) => (
        <text key={`t${k}`} x={p.mid[0]} y={p.mid[1] + 4} textAnchor="middle" className="gf-move">{p.n}곳</text>
      ))}
    </svg>
  );
}

/** D 기울기 차트: 기본 점수 상위 10곳의 점수 변화 */
/** 같은 값끼리 묶은 라벨: 값마다 하나, 위아래 최소 간격을 지키도록 아래로 민다 */
function stackLabels(items: { v: number; name: string }[], y: (v: number) => number, gap = 15) {
  const groups = new Map<number, string[]>();
  for (const it of items) groups.set(it.v, [...(groups.get(it.v) ?? []), it.name]);
  const out = [...groups].sort((a, b) => b[0] - a[0]).map(([v, ns]) => ({ v, ns, ty: y(v) }));
  for (let k = 1; k < out.length; k++) out[k].ty = Math.max(out[k].ty, out[k - 1].ty + gap);
  return out;
}
const short = (s: string, n = 14) => (s.length > n ? `${s.slice(0, n)}…` : s);

/** D 기울기 차트: 기본 점수 상위 10곳의 점수 변화 */
function Slope({ rows }: { rows: { name: string; a: number; b: number; color: string }[] }) {
  if (!rows.length) return null;
  const W = 680, padY = 18, xl = 250, xr = 470;
  const vals = rows.flatMap((r) => [r.a, r.b]);
  const lo = Math.floor(Math.min(...vals) - 1), hi = Math.ceil(Math.max(...vals) + 1);
  const span = 260;
  const y = (v: number) => padY + ((hi - v) / (hi - lo || 1)) * span;
  const left = stackLabels(rows.map((r) => ({ v: r.a, name: r.name })), y);
  const right = stackLabels(rows.map((r) => ({ v: r.b, name: r.name })), y);
  const H = Math.max(span + 2 * padY, ...left.map((l) => l.ty + padY), ...right.map((l) => l.ty + padY));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="slope" role="img" aria-label="기본 점수 상위 10곳의 점수 변화">
      <text x={xl} y={12} textAnchor="middle" className="sl-head">기본</text>
      <text x={xr} y={12} textAnchor="middle" className="sl-head">바꾼 뒤</text>
      <line x1={xl} x2={xl} y1={padY} y2={span + padY} className="axis" />
      <line x1={xr} x2={xr} y1={padY} y2={span + padY} className="axis" />
      {rows.map((r, i) => (
        <g key={i}>
          <line x1={xl} y1={y(r.a)} x2={xr} y2={y(r.b)} stroke={r.color} strokeWidth={2} opacity={0.8} />
          <circle cx={xl} cy={y(r.a)} r={4} fill={r.color} /><circle cx={xr} cy={y(r.b)} r={4} fill={r.color} />
        </g>
      ))}
      {left.map((l) => (
        <text key={`l${l.v}`} x={xl - 10} y={l.ty + 4} textAnchor="end" className="sl-label">
          {short(l.ns[0])}{l.ns.length > 1 ? ` 외 ${l.ns.length - 1}곳` : ""} <tspan className="sl-num">{fmt(l.v)}</tspan>
        </text>
      ))}
      {right.map((l) => (
        <text key={`r${l.v}`} x={xr + 10} y={l.ty + 4} className="sl-label">
          <tspan className="sl-num">{fmt(l.v)}</tspan>{l.ns.length > 1 ? ` (${l.ns.length}곳)` : ""}
        </text>
      ))}
    </svg>
  );
}

function Sensitivity() {
  const search = useSearchParams();
  const { data: regions } = useRegions();
  const { data: rules } = useRules();
  const avail = regions?.regions.filter((r) => r.available) ?? [];
  const [picked, setPicked] = useState<string | null>(null);
  const rid = picked ?? (avail.find((r) => r.region_id === search.get("region"))?.region_id
    ?? avail.find((r) => r.region_id === regions?.default_region_id)?.region_id ?? avail[0]?.region_id ?? null);
  const { data: pdoc, error } = usePoints(rid);
  const [chosen, setChosen] = useState<{ rid: string | null; sc: Scenario } | null>(null);

  const pts = useMemo<Pt[]>(() => (pdoc?.points ?? []).map((p) => ({ key: p.key, name: p.name, r: p.r })), [pdoc]);
  const base = useMemo(() => (rules && pts.length ? scoreAll(pts, rules.rules.map((r) => r.max_points), rules) : null), [pts, rules]);
  // A 토네이도: 8개 기준 × (끄기, 2배)의 등급 변경 비율
  const tornado = useMemo(() => (rules && base ? rules.rules.map((_, i) => ({
    off: outcome(base, pts, rules, { rule: i, mult: 0 }).moved / base.size,
    dbl: outcome(base, pts, rules, { rule: i, mult: 2 }).moved / base.size,
  })) : []), [rules, base, pts]);
  // 처음 보여 줄 경우: 결과를 가장 크게 흔드는 경우 (지역마다 다름)
  const strongest = useMemo<Scenario | null>(() => {
    let best: Scenario | null = null, v = -1;
    tornado.forEach((t, i) => {
      if (t.off > v) { v = t.off; best = { rule: i, mult: 0 }; }
      if (t.dbl > v) { v = t.dbl; best = { rule: i, mult: 2 }; }
    });
    return best;
  }, [tornado]);
  const sc = (chosen?.rid === rid ? chosen?.sc : null) ?? strongest;
  const res = useMemo(() => (rules && base && sc ? outcome(base, pts, rules, sc) : null), [rules, base, pts, sc]);
  const choose = (s: Scenario) => setChosen({ rid, sc: s });
  // 토네이도 막대가 화면에 들어올 때마다(지역을 바꿀 때도) 0부터 자라게
  const [tnRef, tnPlay] = usePlayOnView<HTMLDivElement>(tornado.length ? rid : null);

  if (!rules) return <p className="loading">불러오는 중…</p>;
  const ruleName = (i: number) => `${rules.rules[i].id} ${rules.rules[i].name}`;
  const maxPct = Math.max(0.05, ...tornado.flatMap((t) => [t.off, t.dbl]));
  const pct = res && base ? (100 * res.moved) / base.size : 0;
  const v = verdict(pct);
  const scLabel = sc ? `${ruleName(sc.rule)} 가중치 ${rules.rules[sc.rule].max_points}점 → ${fmt(rules.rules[sc.rule].max_points * sc.mult)}점` : "";
  const gcolor = new Map<string, string>(rules.grades.map((g) => [g.label, g.color]));
  const order = base ? [...base].sort((a, b) => b[1].score - a[1].score || (a[0] < b[0] ? -1 : 1)) : [];
  const names = new Map(pts.map((p) => [p.key, p.name]));

  return (
    <>
      <header className="rules-hero">
        <h1>민감도 분석</h1>
        <p>채점 기준 하나의 가중치를 바꾸면 결과가 얼마나 달라지는지 확인합니다. 결과가 크게 흔들리는 기준일수록 그 가중치를 정한 근거가 중요합니다.
          모든 값은 지도와 같은 채점 공식으로 이 화면에서 바로 계산합니다.</p>
        <label className="field">지역{" "}
          <select value={rid ?? ""} onChange={(e) => setPicked(e.target.value)} style={{ width: "auto" }}>
            {avail.map((r) => <option key={r.region_id} value={r.region_id}>{r.sido} {r.sigungu}</option>)}
          </select>
        </label>
      </header>
      {error && <div className="notice error">지점 데이터를 불러오지 못했습니다.</div>}
      {!base ? <p className="loading">계산하는 중…</p> : (
        <>
          <section>
            <h2><span className="step">1</span> 어떤 기준이 결과를 가장 많이 흔드나</h2>
            <p className="field">막대 = 그 기준의 가중치를 바꿨을 때 등급이 바뀌는 지점 비율. 막대를 누르면 아래에서 자세히 봅니다.</p>
            <div ref={tnRef} className={`tornado${tnPlay ? " grow" : ""}`}>
              <div className="tn-legend"><span><i className="off" />끄기 (×0) ←</span><span className="tn-mid">기준</span><span>→ 2배 (×2)<i className="dbl" /></span></div>
              {rules.rules.map((r, i) => (
                <div key={r.id} className="tn-row" style={{ "--d": `${i * 70}ms` } as CSSProperties}>
                  <button type="button" className={`tn-bar off${sc?.rule === i && sc.mult === 0 ? " on" : ""}`} onClick={() => choose({ rule: i, mult: 0 })}
                    aria-label={`${ruleName(i)} 끄기: ${(100 * tornado[i].off).toFixed(1)}%`}>
                    <span style={{ width: tnPlay ? `${(100 * tornado[i].off) / maxPct}%` : 0 }} /><em>{(100 * tornado[i].off).toFixed(1)}%</em>
                  </button>
                  <span className="tn-label">{r.id} {r.name}{r.is_assumption && <small className="badge assumption">가정</small>}</span>
                  <button type="button" className={`tn-bar dbl${sc?.rule === i && sc.mult === 2 ? " on" : ""}`} onClick={() => choose({ rule: i, mult: 2 })}
                    aria-label={`${ruleName(i)} 2배: ${(100 * tornado[i].dbl).toFixed(1)}%`}>
                    <span style={{ width: tnPlay ? `${(100 * tornado[i].dbl) / maxPct}%` : 0 }} /><em>{(100 * tornado[i].dbl).toFixed(1)}%</em>
                  </button>
                </div>
              ))}
            </div>
          </section>

          {sc && res && (
            <section>
              <h2><span className="step">2</span> 자세히 보기</h2>
              <div className="sc-pick">
                <select value={sc.rule} onChange={(e) => choose({ rule: Number(e.target.value), mult: sc.mult })} aria-label="바꿀 기준">
                  {rules.rules.map((r, i) => <option key={r.id} value={i}>{r.id} {r.name}</option>)}
                </select>
                <div className="seg" role="group" aria-label="배율">
                  {MULTS.map((m) => (
                    <button key={m} type="button" aria-pressed={sc.mult === m} onClick={() => choose({ rule: sc.rule, mult: m })}>{MULT_LABEL[m]}</button>
                  ))}
                </div>
              </div>
              <div className={`sens-answer ${v.cls}`}>
                <p className="q">{scLabel}으로 바꾸면?</p>
                <p className="a">위험 상위 {TOP_N}곳 중 <b>{res.topKeep}곳</b>이 그대로이고, 등급이 바뀐 지점은 {base.size.toLocaleString()}곳 중 <b>{res.moved.toLocaleString()}곳({pct.toFixed(1)}%)</b>입니다.
                  <span className="verdict">{v.text}</span></p>
              </div>
              <div className="kpis">
                <div><b>{res.topKeep} / {TOP_N}</b><span>위험 상위 {TOP_N}곳 중 그대로 남은 곳</span></div>
                <div><b>{res.moved.toLocaleString()}곳</b><span>등급이 바뀐 지점 ({pct.toFixed(1)}%)</span></div>
                <div><b>{fmt(Math.round(res.meanAbs * 100) / 100)}점</b><span>지점당 평균 점수 변화</span></div>
              </div>
              <h3 className="sub">등급이 어디로 움직였나</h3>
              <GradeFlow flows={res.flows} grades={rules.grades} leftLabel="기본 가중치" rightLabel="바꾼 가중치" />

              <details className="more">
                <summary>더 보기 — 점수 산점도, 상위 10곳 점수 변화, 상위 {TOP_N}곳 표</summary>
                <h3 className="sub">점수 산점도 (가로: 기본, 세로: 바꾼 가중치)</h3>
                <p className="field">점선(대각선)에 붙어 있으면 점수가 거의 안 바뀐 지점입니다. 색은 바뀐 뒤 등급, 테두리가 있는 점은 등급이 바뀐 지점입니다.</p>
                <div className="chart-card">
                  <ResponsiveContainer width="100%" height={340}>
                    <ScatterChart margin={{ top: 10, right: 20, bottom: 24, left: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" dataKey="a" domain={[0, 100]} name="기본" label={{ value: "기본 점수", position: "insideBottom", offset: -12 }} />
                      <YAxis type="number" dataKey="b" domain={[0, 100]} name="바꾼 뒤" />
                      <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} strokeDasharray="5 4" stroke="var(--text-muted)" />
                      <Tooltip cursor={false} formatter={(val) => fmt(Number(val))} />
                      {rules.grades.map((g) => (
                        <Scatter key={g.label} isAnimationActive={false} fill={g.color}
                          data={[...base].flatMap(([k, a]) => {
                            const b = res.scores.get(k);
                            return b && b.grade === g.label ? [{ a: a.score, b: b.score, moved: a.grade !== b.grade }] : [];
                          })}
                          shape={(p: { cx?: number; cy?: number; payload?: { moved: boolean } }) => (
                            <circle cx={p.cx} cy={p.cy} r={4} fill={g.color} stroke={p.payload?.moved ? "#1f2937" : "none"} strokeWidth={1.5} />
                          )} />
                      ))}
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
                <h3 className="sub">기본 점수 상위 10곳의 점수 변화</h3>
                <div className="chart-card">
                  <Slope rows={order.slice(0, 10).map(([k, a]) => {
                    const b = res.scores.get(k)!;
                    return { name: names.get(k) ?? k, a: a.score, b: b.score, color: gcolor.get(b.grade) ?? "var(--accent)" };
                  })} />
                </div>
                <h3 className="sub">기본 점수 상위 {TOP_N}곳</h3>
                <p className="field">같은 점수인 지점이 많아 순위는 작은 점수 변화에도 크게 움직일 수 있어, 점수와 등급으로 비교합니다.</p>
                <table>
                  <thead><tr><th>장소</th><th>기본 점수</th><th>바꾼 뒤</th><th>변화</th><th>등급</th></tr></thead>
                  <tbody>
                    {order.slice(0, TOP_N).map(([k, a]) => {
                      const b = res.scores.get(k)!;
                      const d = Math.round((b.score - a.score) * 100) / 100;
                      return (
                        <tr key={k}>
                          <td>{names.get(k) ?? k}</td><td>{fmt(a.score)}</td><td>{fmt(b.score)}</td>
                          <td>{d > 0 ? <span className="up">▲{fmt(d)}</span> : d < 0 ? <span className="down">▼{fmt(-d)}</span> : "–"}</td>
                          <td>{a.grade}{a.grade !== b.grade && ` → ${b.grade}`}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </details>
            </section>
          )}
        </>
      )}
    </>
  );
}

export default function SensitivityPage() {
  return (
    <DocShell>
      <Suspense fallback={<p className="loading">불러오는 중…</p>}><Sensitivity /></Suspense>
    </DocShell>
  );
}
