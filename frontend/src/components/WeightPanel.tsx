"use client";
// R1~R8 [체크] + [슬라이더 0~2×max] + 가정 배지 + 기본값 (plan.md §9.3)
import * as Slider from "@radix-ui/react-slider";
import type { RulesDoc } from "@/lib/types";
import { useAppStore } from "@/store/useAppStore";

export function WeightPanel({ rules }: { rules: RulesDoc }) {
  const { weights, selected, setWeight, toggleRule, resetWeights } = useAppStore();
  if (!weights.length) return null;
  return (
    <section className="panel">
      <h2>위험요인 선택·가중치 <button type="button" onClick={resetWeights}>기본값으로</button></h2>
      <div className="weight-panel">
        {rules.rules.map((r, i) => (
          <div key={r.id} className={`rule ${selected[i] ? "" : "off"}`}>
            <input type="checkbox" id={`sel-${r.id}`} checked={selected[i]} onChange={() => toggleRule(i)}
              aria-label={`${r.id} 선택`} />
            <label htmlFor={`sel-${r.id}`} className="name">
              {r.id} {r.name} {r.is_assumption && <span className="badge assumption" title="가정 기반 규칙">가정</span>}
            </label>
            <span />
            <Slider.Root className="slider-root" min={0} max={2 * r.max_points} step={1} value={[weights[i]]}
              onValueChange={([v]) => setWeight(i, v)} disabled={!selected[i]} aria-label={`${r.id} 가중치`}>
              <Slider.Track className="slider-track"><Slider.Range className="slider-range" /></Slider.Track>
              <Slider.Thumb className="slider-thumb" aria-label={`${r.id} 가중치`} />
            </Slider.Root>
            <output>{weights[i]}</output>
            <div className="one-liner">{r.one_liner} (기본 {r.max_points}점)</div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ScoreNotice({ error, warnings }: { error: string | null; warnings: string[] }) {
  if (error === "TOO_FEW_RULES") return <div className="notice error">위험요인을 2개 이상 선택해야 점수를 계산합니다.</div>;
  if (error === "ZERO_WEIGHT") return <div className="notice error">선택한 위험요인의 가중치 합이 0입니다. 가중치를 올려 주세요.</div>;
  if (warnings.includes("LOW_MAXSUM"))
    return <div className="notice warn">선택한 요인의 만점 합이 작아 점수가 소수 요인에 크게 좌우됩니다.</div>;
  return null;
}
