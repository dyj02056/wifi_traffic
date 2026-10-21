"use client";
// 순위 변동 표: 지역 전체 순위에서 상위 20(내림차순) 또는 하위 20(오름차순), 기본 기준 순위와 비교
// — 행이 미끄러지며 재정렬, ▲▼ 색 플래시 (plan.md §9.2)
//
// [이 파일이 하는 일]
//   지도 옆 '순위 변동' 표를 그립니다. 가중치를 바꾸면 순위가 다시 계산되고,
//   기본 기준일 때의 순위(baseRank)보다 올랐으면 ▲(초록 깜빡임), 내렸으면 ▼(빨강 깜빡임)로 보여 줍니다.
//   motion 도구로 행이 제자리를 찾아 미끄러지듯 움직이며, '움직임 줄이기' 설정이면 애니메이션을 끕니다.
//   순위 계산 자체는 MapScreen.tsx가 하고, 이 부품은 받은 rows를 그리기만 합니다.
import { AnimatePresence, motion } from "motion/react";
import { usePrefersReducedMotion } from "@/lib/queries";
import { fmt } from "./format";

// 표 한 줄: key(지점키), name(장소명), score(현재 점수), rank(현재 순위), baseRank(기본 기준 순위), color(등급 색)
export interface RankRow { key: string; name: string; score: number; baseRank: number; color: string; rank: number }

// 받는 값: overlap(기본 기준 상위 N과 겹치는 수), order(desc=점수 높은 순/asc=낮은 순), onOrder(정렬 바꾸기),
//          onClick(줄을 누르면 그 지점 상세 열기), onCollapse(표 접기 버튼, 없으면 버튼 숨김)
export function RankTable({ rows, overlap, topN, total, order, onOrder, onClick, onCollapse }: {
  rows: RankRow[]; overlap: number; topN: number; total: number; order: "desc" | "asc"; onOrder: (o: "desc" | "asc") => void;
  onClick: (key: string) => void; onCollapse?: () => void;
}) {
  const reduce = usePrefersReducedMotion();
  const edge = order === "desc" ? "상위" : "하위";
  return (
    <section className="rank-table">
      <h2 className="map-head">순위 변동 (전체 {total.toLocaleString()}곳 중 {edge} {topN})
        {onCollapse && <button type="button" className="collapse-btn" onClick={onCollapse} aria-label="순위 변동 접기" title="접기">▸</button>}
      </h2>
      <div className="sort-toggle" role="group" aria-label="정렬">
        <button type="button" aria-pressed={order === "desc"} onClick={() => onOrder("desc")}>↓ 내림차순 <small>상위 {topN}</small></button>
        <button type="button" aria-pressed={order === "asc"} onClick={() => onOrder("asc")}>↑ 오름차순 <small>하위 {topN}</small></button>
      </div>
      <p className="field overlap">{rows.length ? `기본 기준 ${edge} ${topN}과 겹침 ${overlap}개` : ""}</p>
      <table>
        <thead><tr><th className="num">순위</th><th>장소</th><th className="num">점수</th><th className="num">기본</th><th className="num">변동</th></tr></thead>
        <tbody>
          <AnimatePresence initial={false}>
            {rows.map((r) => {
              // d > 0: 기본 기준보다 순위가 올라감(숫자가 작아짐), d < 0: 내려감
              const d = r.baseRank - r.rank;
              return (
                <motion.tr key={r.key} layout={!reduce} initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }}
                  exit={reduce ? undefined : { opacity: 0 }} transition={{ duration: 0.35 }}
                  className={d > 0 ? "flash-up" : d < 0 ? "flash-down" : ""} onClick={() => onClick(r.key)}>
                  <td className="num">{r.rank}</td>
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
