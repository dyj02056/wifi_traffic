"use client";
// 지점 상세: 오른쪽(모바일은 아래)에서 슬라이드 인, R1~R8 막대가 순서대로 채워짐(stagger 50ms) (plan.md §9.2)
import type { CSSProperties } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { Detail, RulesDoc } from "@/lib/types";
import { usePrefersReducedMotion } from "@/lib/queries";
import { DISCLAIMER } from "./DisclaimerBar";
import { EVIDENCE_LABELS, FLAG_LABELS, fmt } from "./format";

interface Props {
  detail: Detail | null | undefined;
  loading: boolean;
  open: boolean;
  rules: RulesDoc;
  weights: number[];
  selected: boolean[];
  current: { score: number | null; grade: string | null } | undefined;
  onClose: () => void;
}

export function PointSheet({ detail, loading, open, rules, weights, selected, current, onClose }: Props) {
  const reduce = usePrefersReducedMotion();
  const wsum = rules.rules.reduce((a, _, i) => a + (selected[i] ? weights[i] : 0), 0);
  const g = rules.grades.find((x) => x.label === current?.grade);
  return (
    <AnimatePresence>
      {open && (
        <motion.section key="sheet" className="point-sheet open" aria-live="polite"
          initial={reduce ? false : { x: "100%" }} animate={{ x: 0 }} exit={reduce ? undefined : { x: "100%" }}
          transition={{ type: "spring", stiffness: 320, damping: 34 }}>
          <div className="sheet-inner">
            <button className="close" aria-label="닫기" onClick={onClose}>✕</button>
            {loading || !detail ? <p className="loading">{loading ? "불러오는 중…" : "지점 정보를 찾지 못했습니다."}</p> : (
              <>
                {/* 머리 부분: 등급색 바탕 + 신호등(해당 등급 불만 켜짐) (E) */}
                <div className="sheet-head" style={{ "--c": g?.color ?? "var(--grade-none)" } as CSSProperties}>
                  <div className="signal" aria-hidden="true">
                    {[...rules.grades].reverse().map((x) => (
                      <span key={x.label} className={x.label === g?.label ? "on" : ""} style={{ "--lamp": x.color } as CSSProperties} />
                    ))}
                  </div>
                  <div className="head-text">
                    <h2>{detail.name}</h2>
                    <span className="score-big">{current?.score != null ? fmt(current.score) : "계산 중지"}</span>
                    {g && <span className="grade-label">{g.label}</span>}
                  </div>
                </div>
                <div className="sheet-disclaimer">※ {DISCLAIMER}</div>
                <div className="reason">현재 가중치 기준 · 기본 가중치 기준 {fmt(detail.score)}점({detail.grade})</div>
                <section className="panel breakdown">
                  <h3>위험요인별 점수 (R1~R8)</h3>
                  {detail.breakdown.map((b, i) => {
                    const on = selected[i] && wsum > 0;
                    const contrib = on ? (100 * weights[i] * b.ratio) / wsum : 0;
                    return (
                      <div key={b.id} className={`row ${on ? "" : "off"}`}>
                        <div className="head">
                          <span>{b.id} {b.name} {b.is_assumption && <span className="badge assumption">가정</span>}</span>
                          <span>{on ? `${fmt(Math.floor(contrib * 100 + 0.5) / 100)}점` : "미선택"} · 비율 {fmt(b.ratio)}</span>
                        </div>
                        <div className="bar">
                          <motion.span initial={reduce ? false : { width: 0 }} animate={{ width: `${(b.ratio * 100).toFixed(1)}%` }}
                            transition={{ delay: reduce ? 0 : i * 0.05, duration: 0.4 }} />
                        </div>
                        <div className="reason">{b.reason}</div>
                      </div>
                    );
                  })}
                </section>
                <section className="panel">
                  <h3>설명</h3>
                  <motion.div className="explanation" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }}>
                    {detail.explanation.text}
                    <div className="src">{detail.explanation.source === "ai" ? "AI 생성(근거값만 인용·검증 통과)" : "근거값 기반 자동 설명"}</div>
                  </motion.div>
                </section>
                <section className="panel">
                  <h3>안전하게 쓰는 법</h3>
                  <ul className="tips">
                    {detail.safety_tips.map((t, i) => <li key={i}><label><input type="checkbox" /> {t}</label></li>)}
                  </ul>
                </section>
                <section className="panel">
                  <h3>신고·문의</h3>
                  <p>{detail.report_contact.manager ?? "관리기관 정보 없음"}{" "}
                    {detail.report_contact.tel ? <>· <a href={`tel:${detail.report_contact.tel}`}>{detail.report_contact.tel}</a></> : "· 전화번호 없음"}</p>
                </section>
                <section className="panel">
                  <h3>근거값 (원본 데이터)</h3>
                  <dl className="evidence">
                    {Object.entries(detail.evidence).map(([k, v]) => (
                      <div key={k} style={{ display: "contents" }}>
                        <dt>{EVIDENCE_LABELS[k] ?? k}</dt><dd>{v == null || v === "" ? <em>없음</em> : String(v)}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
                <section className="panel">
                  <h3>데이터 참고</h3>
                  {detail.flags.length ? <ul>{detail.flags.map((f) => <li key={f}>{FLAG_LABELS[f] ?? f}</li>)}</ul> : <p>없음</p>}
                </section>
              </>
            )}
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}
