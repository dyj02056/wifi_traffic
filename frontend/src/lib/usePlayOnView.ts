"use client";
// 화면에 들어올 때마다 그래프를 0부터 다시 그리기 위한 신호 (배경 통계 막대, 민감도 토네이도).
import { useEffect, useRef, useState } from "react";

/** 이 화면에 들어올 때마다 요소 윗부분이 보이는 순간 play가 1씩 오른다(0이면 아직 안 보임).
 * cacheComponents(next.config)가 다녀간 화면을 숨겨 둔 채 보관하므로, 숨길 때(effect 정리) 0으로 되돌리고
 * 다시 보일 때(effect 재실행) 새 번호를 줘서 그래프가 매번 0부터 자라게 한다.
 * IntersectionObserver가 안 도는 환경이 있어 위치를 직접 잰다.
 * trigger: 요소가 늦게 생기거나(데이터 로딩) 내용이 바뀔 때(지역 변경) 넘기면 그때 다시 잰다. null이면 기다린다. */
export function usePlayOnView<T extends Element>(trigger: unknown = true) {
  const ref = useRef<T>(null);
  const [play, setPlay] = useState(0);
  const runs = useRef(0);
  useEffect(() => {
    if (trigger == null) return;
    let done = false;
    const check = () => {
      const b = ref.current?.getBoundingClientRect();
      if (done || !b || !(b.top < innerHeight * 0.85 && b.bottom > 0)) return;
      done = true;
      setPlay(++runs.current);
    };
    const raf = requestAnimationFrame(check);
    // 스크롤은 창이 아니라 main.doc 안에서 일어나고 scroll 이벤트는 위로 전달되지 않으므로 capture로 받는다
    addEventListener("scroll", check, { passive: true, capture: true });
    addEventListener("resize", check);
    return () => {
      cancelAnimationFrame(raf);
      removeEventListener("scroll", check, { capture: true });
      removeEventListener("resize", check);
      setPlay(0);
    };
  }, [trigger]);
  return [ref, play] as const;
}

/** 사용자가 움직임 줄이기를 켰는지 (처음 한 번만 읽음) */
export function useStill() {
  const [still] = useState(() => typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches);
  return still;
}
