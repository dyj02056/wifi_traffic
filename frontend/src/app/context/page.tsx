"use client";
// 배경 통계·사례 카드 (plan.md §9.3 /context) — "점수 미반영" 고정, 차트마다 출처·날짜
// 차트는 화면에 들어올 때마다 새로 그려서 막대가 0에서 값까지 자라는 모습이 보이게 한다(유형별로 아래부터 차례로 쌓임).
//
// [이 파일이 하는 일]
//   "/context" 화면: 경찰청·KISA 통계를 막대그래프로, 같은 원리의 해외·국내 사건을 접었다 펼치는 카드로 보여 줍니다.
//   이 통계와 사례는 '왜 위험요인을 살펴봐야 하나'를 설명하는 참고 자료일 뿐, 지점 점수에는 쓰지 않습니다.
//   그래프는 recharts 도구로 그립니다. 한 해에 여러 유형이 있으면 막대를 위로 쌓아(stack) 보여 줍니다.
import type { ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DocShell, SourceNote } from "@/components/DocShell";
import { useBackground, useCases } from "@/lib/queries";
import type { BackgroundDoc } from "@/lib/types";
import { usePlayOnView, useStill } from "@/lib/usePlayOnView";

type Dataset = BackgroundDoc["datasets"][number];

// [위 색, 아래 색] — 막대마다 위에서 아래로 옅어지는 그라데이션
const PALETTE: [string, string][] = [
  ["#3b6ff0", "#1d47b8"], ["#f06464", "#c23434"], ["#f5c33b", "#d49a00"],
  ["#3fbf7f", "#23874f"], ["#8b5cf6", "#5b21b6"], ["#22a5c3", "#0e6f86"],
];
// 막대가 자라는 시간(0.9초), 유형별로 시작을 늦추는 간격(0.25초)
const GROW_MS = 900, STEP_MS = 250;

const fmtN = (v: number) => Math.round(v).toLocaleString();

/** 그래프 아래 '이 그래프가 말해 주는 것' — 숫자는 모두 이 데이터에서 계산한다(지어내지 않기) */
function describe(ds: Dataset): ReactNode {
  if (ds.id !== "police_hacking_by_year") return null;
  const years = [...new Set(ds.series.map((p) => p.label))].sort();
  if (years.length < 2) return null;
  const first = years[0], last = years.at(-1)!;
  const total = (y: string) => ds.series.filter((p) => p.label === y).reduce((a, p) => a + p.value, 0);
  const a = total(first), b = total(last);
  const lastRows = ds.series.filter((p) => p.label === last).sort((x, y) => y.value - x.value);
  const top = lastRows[0];
  const topFirst = ds.series.find((p) => p.label === first && p.group === top.group)?.value;
  return (
    <>
      <p><b>{first}년 {fmtN(a)}건</b>이던 해킹 발생 건수가 <b>{last}년 {fmtN(b)}건</b>으로 약 <b>{(b / a).toFixed(1)}배</b>가 됐습니다.
        {top.group && <> {last}년에 가장 많은 유형은 <b>&apos;{top.group}&apos;({fmtN(top.value)}건)</b>
          {topFirst ? <>으로, {first}년({fmtN(topFirst)}건)의 약 {(top.value / topFirst).toFixed(1)}배입니다.</> : <>입니다.</>}</>}</p>
      {top.group === "계정도용" && (
        <p>계정도용은 다른 사람의 아이디·비밀번호를 빼내 쓰는 범죄입니다. 비밀번호 없이 연결되는 개방형 와이파이나
          진짜와 이름이 같은 가짜 와이파이에서 로그인하면 이런 정보가 새어 나갈 수 있습니다.
          (이 통계가 모두 와이파이에서 일어났다는 뜻은 아닙니다.)</p>
      )}
      <ul>
        <li>같은 장소에 <b>보안접속(Secure) SSID</b>가 보이면 그쪽으로 연결하세요.</li>
        <li>로그인·결제처럼 중요한 일은 <b>모바일 데이터나 개인 핫스팟</b>으로 하세요.</li>
        <li>와이파이 접속 화면에서 <b>앱 설치나 업데이트를 요구하면</b> 바로 연결을 끊으세요.</li>
      </ul>
    </>
  );
}

// 통계 하나를 막대그래프 카드로 그린다
function Chart({ ds }: { ds: Dataset }) {
  const [ref, play] = usePlayOnView<HTMLElement>();
  const still = useStill();
  const groups = [...new Set(ds.series.map((p) => p.group ?? ds.unit))];
  // series(막대 하나씩 나열된 목록)를 가로축 이름(label)별 한 줄로 모은다.
  // 예) {label:"2023", 계정도용: 120, 기타: 30, _total: 150} — recharts가 이 모양을 받아 쌓인 막대를 그린다
  const rows = new Map<string, Record<string, string | number>>();
  for (const p of ds.series) {
    const row = rows.get(p.label) ?? { label: p.label, _total: 0 };
    row[p.group ?? ds.unit] = p.value;
    row._total = (row._total as number) + p.value;
    rows.set(p.label, row);
  }
  const story = describe(ds);
  const gid = (i: number) => `g-${ds.id}-${i}`;
  return (
    <section ref={ref} className={`chart-card reveal${play ? " in" : ""}`}>
      <h2 className="subhead">{ds.title}</h2>
      <div style={{ height: 320 }}>
        {play > 0 && (
          <ResponsiveContainer key={play} width="100%" height={320}>
            <BarChart data={[...rows.values()]} margin={{ top: 24, right: 12, bottom: 4, left: 0 }} barCategoryGap="22%">
              <defs>
                {groups.map((_, i) => (
                  <linearGradient key={i} id={gid(i)} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={PALETTE[i % PALETTE.length][0]} />
                    <stop offset="100%" stopColor={PALETTE[i % PALETTE.length][1]} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid stroke="#eef0f3" vertical={false} />
              <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: "#d9dee4" }} tick={{ fill: "#5b6573", fontSize: 12 }} />
              <YAxis tickFormatter={(v: number) => v.toLocaleString()} tickLine={false} axisLine={false} width={52}
                tick={{ fill: "#8a94a3", fontSize: 11 }} />
              <Tooltip cursor={{ fill: "rgba(36, 89, 214, .07)", radius: 8 }}
                contentStyle={{ borderRadius: 10, border: "1px solid #e6e8ec", boxShadow: "0 6px 20px rgba(16,24,40,.12)" }}
                formatter={(v) => `${Number(v).toLocaleString()}${ds.unit}`} />
              {groups.length > 1 && <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 6 }} />}
              {groups.map((g, i) => {
                const topmost = i === groups.length - 1;
                return (
                  <Bar key={g} dataKey={g} stackId="a" fill={`url(#${gid(i)})`} maxBarSize={44}
                    radius={topmost ? [8, 8, 0, 0] : groups.length === 1 ? [8, 8, 0, 0] : 0}
                    stroke="#fff" strokeWidth={groups.length > 1 ? 1 : 0}
                    isAnimationActive={!still} animationBegin={i * STEP_MS} animationDuration={GROW_MS} animationEasing="ease-out">
                    {topmost && (
                      <LabelList dataKey="_total" position="top" offset={6}
                        formatter={(v) => Number(v).toLocaleString()}
                        style={{ fontSize: 11, fontWeight: 700, fill: "#1c2430" }} />
                    )}
                  </Bar>
                );
              })}
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
      {story && <div className="chart-story"><h3>이 그래프가 말해 주는 것</h3>{story}</div>}
      {ds.note && <p className="field">{ds.note}</p>}
      <SourceNote name={ds.source.name} url={ds.source.url} retrieved={ds.source.retrieved_at} published={ds.source.published_at} />
    </section>
  );
}

// 페이지 본체: 안내 문구 → 통계 차트들 → 사례 카드 목록
export default function ContextPage() {
  const bg = useBackground();
  const cases = useCases();
  return (
    <DocShell>
      <header className="rules-hero">
        <h1>배경 통계·사례</h1>
        <p>공공와이파이 위험요인을 왜 살펴봐야 하는지 보여 주는 국내 해킹·침해사고 통계와, 같은 원리로 일어난 실제 사건 사례입니다.
          지점 점수와는 별개의 참고 자료입니다.</p>
      </header>
      <div className="fixed-notice">{bg.data?.notice ?? "이 통계는 지점 점수에 반영하지 않습니다"}</div>
      {bg.error && <div className="notice error">배경 통계를 불러오지 못했습니다.</div>}
      {bg.data && (bg.data.datasets.length
        ? bg.data.datasets.map((ds) => <Chart key={ds.id} ds={ds} />)
        : <p className="loading">배경 통계 준비 중입니다.</p>)}

      <section>
        <h2 className="subhead">{cases.data?.label ?? "같은 원리 사례 — 국내 공공와이파이 사건 아님"}</h2>
        {cases.data && (cases.data.cases.length ? (
          <div className="case-list">
            {cases.data.cases.map((c) => (
              <details key={c.id} className="case-row">
                <summary>
                  <span className="case-title">{c.title}</span>
                  <span className="case-rules">{c.related_rules.map((r) => <span key={r}>{r}</span>)}</span>
                </summary>
                <div className="case-body">
                  <p>{c.summary}</p>
                  <p className="principle">원리: {c.principle} · 관련 항목 {c.related_rules.join(", ")}</p>
                  <SourceNote name={c.source.name} url={c.source.url} retrieved={c.source.retrieved_at} published={c.source.published_at} />
                </div>
              </details>
            ))}
          </div>
        ) : <p className="loading">사례 카드 준비 중입니다(요약 작성 대기).</p>)}
      </section>
    </DocShell>
  );
}
