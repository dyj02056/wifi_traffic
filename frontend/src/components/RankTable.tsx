"use client";
// 순위 변동 표: 기본 기준 상위 20 vs 현재 상위 20 — 행이 미끄러지며 재정렬, ▲▼ 색 플래시 (plan.md §9.2)
import { AnimatePresence, motion } from "motion/react";
import { usePrefersReducedMotion } from "@/lib/queries";
import { fmt } from "./format";

export interface RankRow { key: string; name: string; score: number; baseRank: number; color: string }

export function RankTable({ rows, overlap, topN, onClick }: {
  rows: RankRow[]; overlap: number; topN: number; onClick: (key: string) => void;
}) {
  const reduce = usePrefersReducedMotion();
  return (
    <section className="rank-table">
      <h2>순위 변동 (현재 기준 상위 {topN})</h2>
      <p className="field overlap">{rows.length ? `기본 기준 상위 ${topN}과 겹침 ${overlap}개` : ""}</p>
      <table>
        <thead><tr><th className="num">순위</th><th>장소</th><th className="num">점수</th><th className="num">기본</th><th className="num">변동</th></tr></thead>
        <tbody>
          <AnimatePresence initial={false}>
            {rows.map((r, i) => {
              const d = r.baseRank - (i + 1);
              return (
                <motion.tr key={r.key} layout={!reduce} initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }}
                  exit={reduce ? undefined : { opacity: 0 }} transition={{ duration: 0.35 }}
                  className={d > 0 ? "flash-up" : d < 0 ? "flash-down" : ""} onClick={() => onClick(r.key)}>
                  <td className="num">{i + 1}</td>
                  <td><span className="dot" style={{ background: r.color }} />{r.name}</td>
                  <td className="num">{fmt(r.score)}</td>
                  <td className="num">{r.baseRank}</td>
                  <td className="num">{d > 0 ? <span className="up">▲{d}</span> : d < 0 ? <span className="down">▼{-d}</span> : "–"}</td>
                </motion.tr>
              );
            })}
          </AnimatePresence>
        </tbody>
      </table>
    </section>
  );
}
