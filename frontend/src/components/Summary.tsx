"use client";
// 상단 요약: 지점 수·등급별 개수(카운트업)·평균 (plan.md §9.2)
import { useEffect, useRef } from "react";
import { usePrefersReducedMotion } from "@/lib/queries";
import { fmt } from "./format";

const DURATION_MS = 400;

/** 숫자 카운트업. 애니메이션이 끊겨도(백그라운드 탭 등) 마지막에는 항상 실제 값을 보여 준다. */
function CountUp({ value }: { value: number }) {
  const reduce = usePrefersReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const last = useRef(value);
  useEffect(() => {
    const el = ref.current;
    const from = last.current;
    last.current = value;
    if (!el) return;
    const final = () => { el.textContent = value.toLocaleString(); };
    if (reduce || document.hidden || from === value) return final();
    const t0 = performance.now();
    let raf = requestAnimationFrame(function step(t) {
      const k = Math.min(1, (t - t0) / DURATION_MS);
      el.textContent = Math.round(from + (value - from) * k).toLocaleString();
      if (k < 1) raf = requestAnimationFrame(step);
    });
    const done = setTimeout(final, DURATION_MS + 200);
    return () => { cancelAnimationFrame(raf); clearTimeout(done); final(); };
  }, [value, reduce]);
  return <span ref={ref} className="num">{value.toLocaleString()}</span>;
}

export function Summary({ total, counts, grades, avg }: {
  total: number; counts: Record<string, number>; grades: { label: string; emoji: string }[]; avg: number | null;
}) {
  return (
    <div className="summary">
      <span>지점 <span className="num">{total.toLocaleString()}</span></span>
      {grades.map((g) => <span key={g.label}>{g.emoji} {g.label} <CountUp value={counts[g.label] ?? 0} /></span>)}
      <span>평균 <span className="num">{avg == null ? "–" : fmt(avg)}</span>점</span>
    </div>
  );
}
