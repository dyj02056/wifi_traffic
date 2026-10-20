"use client";
// 민감도 분석 — 기준 A(기본) vs 기준 B(R1 30→15) 순위 변화 표·요약·산점도 (plan.md §9.3)
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { DocShell } from "@/components/DocShell";
import { fmt } from "@/components/format";
import { useRegions, useSensitivity } from "@/lib/queries";

function Sensitivity() {
  const search = useSearchParams();
  const { data: regions } = useRegions();
  const avail = regions?.regions.filter((r) => r.available) ?? [];
  const [picked, setPicked] = useState<string | null>(null);
  const rid = picked ?? (avail.find((r) => r.region_id === search.get("region"))?.region_id
    ?? avail.find((r) => r.region_id === regions?.default_region_id)?.region_id ?? avail[0]?.region_id ?? null);
  const { data: s, error } = useSensitivity(rid);

  return (
    <>
      <h1>민감도 분석</h1>
      <p>가중치를 바꾸면 순위가 얼마나 흔들리는지 확인합니다. 점수는 기준에 따라 달라지는 위험요인 지표입니다.</p>
      <label className="field">지역{" "}
        <select value={rid ?? ""} onChange={(e) => setPicked(e.target.value)} style={{ width: "auto" }}>
          {avail.map((r) => <option key={r.region_id} value={r.region_id}>{r.sido} {r.sigungu}</option>)}
        </select>
      </label>
      {error && <div className="notice error">민감도 데이터를 불러오지 못했습니다.</div>}
      {s && (
        <>
          <p>기준 A: {s.scenario_a.label} · 기준 B: {s.scenario_b.label}</p>
          <div className="stat-cards">
            <div>지점 수<b>{s.summary.count.toLocaleString()}</b></div>
            <div>상위 {s.summary.top_n} 겹침<b>{s.summary.top_overlap}개</b></div>
            <div>순위 상관(Spearman)<b>{s.summary.spearman == null ? "–" : s.summary.spearman.toFixed(3)}</b></div>
            <div>등급이 바뀐 지점<b>{s.summary.grade_moves.toLocaleString()}</b></div>
          </div>
          <section className="chart-card">
            <h2>순위 산점도 (A 순위 vs B 순위)</h2>
            <ResponsiveContainer width="100%" height={320}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" dataKey="rank_A" name="기준 A 순위" label={{ value: "기준 A 순위", position: "insideBottom", offset: -10 }} />
                <YAxis type="number" dataKey="rank_B" name="기준 B 순위" reversed />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={s.rows} fill="var(--accent)" isAnimationActive={false} />
              </ScatterChart>
            </ResponsiveContainer>
          </section>
          <section>
            <h2>순위 변화 (기준 A 상위 {s.summary.top_n})</h2>
            <table>
              <thead><tr><th>장소</th><th>A 순위</th><th>B 순위</th><th>변동</th><th>A 점수</th><th>B 점수</th><th>등급 A→B</th></tr></thead>
              <tbody>
                {s.rows.slice(0, s.summary.top_n).map((r) => (
                  <tr key={r.key}>
                    <td>{r.place_name ?? r.key}</td><td>{r.rank_A}</td><td>{r.rank_B}</td>
                    <td>{r.delta > 0 ? <span className="up">▲{r.delta}</span> : r.delta < 0 ? <span className="down">▼{-r.delta}</span> : "–"}</td>
                    <td>{fmt(r.score_A)}</td><td>{fmt(r.score_B)}</td><td>{r.grade_A}{r.grade_A !== r.grade_B && ` → ${r.grade_B}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
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
