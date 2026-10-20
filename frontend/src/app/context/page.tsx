"use client";
// 배경 통계·사례 카드 (plan.md §9.3 /context) — "점수 미반영" 고정, 차트마다 출처·날짜
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DocShell, SourceNote } from "@/components/DocShell";
import { useBackground, useCases } from "@/lib/queries";
import type { BackgroundDoc } from "@/lib/types";

const PALETTE = ["#2459d6", "#d64545", "#e0a800", "#2e9e5b", "#6d28d9", "#0e7490"];

function Chart({ ds }: { ds: BackgroundDoc["datasets"][number] }) {
  const groups = [...new Set(ds.series.map((p) => p.group ?? ds.unit))];
  const rows = new Map<string, Record<string, string | number>>();
  for (const p of ds.series) {
    const row = rows.get(p.label) ?? { label: p.label };
    row[p.group ?? ds.unit] = p.value;
    rows.set(p.label, row);
  }
  return (
    <section className="chart-card">
      <h2>{ds.title}</h2>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={[...rows.values()]} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" />
          <YAxis tickFormatter={(v: number) => v.toLocaleString()} />
          <Tooltip formatter={(v) => `${Number(v).toLocaleString()}${ds.unit}`} />
          {groups.length > 1 && <Legend />}
          {groups.map((g, i) => <Bar key={g} dataKey={g} stackId="a" fill={PALETTE[i % PALETTE.length]} isAnimationActive={false} />)}
        </BarChart>
      </ResponsiveContainer>
      {ds.note && <p className="field">{ds.note}</p>}
      <SourceNote name={ds.source.name} url={ds.source.url} retrieved={ds.source.retrieved_at} published={ds.source.published_at} />
    </section>
  );
}

export default function ContextPage() {
  const bg = useBackground();
  const cases = useCases();
  return (
    <DocShell>
      <h1>배경 통계·사례</h1>
      <div className="fixed-notice">{bg.data?.notice ?? "이 통계는 지점 점수에 반영하지 않습니다"}</div>
      {bg.error && <div className="notice error">배경 통계를 불러오지 못했습니다.</div>}
      {bg.data && (bg.data.datasets.length
        ? bg.data.datasets.map((ds) => <Chart key={ds.id} ds={ds} />)
        : <p className="loading">배경 통계 준비 중입니다.</p>)}

      <h2>{cases.data?.label ?? "같은 원리 사례 — 국내 공공와이파이 사건 아님"}</h2>
      {cases.data && (cases.data.cases.length ? (
        <div className="case-grid">
          {cases.data.cases.map((c) => (
            <article key={c.id} className="case-card">
              <h3>{c.title}</h3>
              <p>{c.summary}</p>
              <p className="principle">원리: {c.principle} · 관련 항목 {c.related_rules.join(", ")}</p>
              <SourceNote name={c.source.name} url={c.source.url} retrieved={c.source.retrieved_at} published={c.source.published_at} />
            </article>
          ))}
        </div>
      ) : <p className="loading">사례 카드 준비 중입니다(요약 작성 대기).</p>)}
    </DocShell>
  );
}
