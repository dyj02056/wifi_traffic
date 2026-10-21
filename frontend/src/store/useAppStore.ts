// 지도 화면 상태: 가중치·선택 규칙·등급 필터·선택 지점·레이어 (plan.md §9.1)
//
// [이 파일이 하는 일]
//   지도 화면의 여러 부품(가중치 패널, 지도, 순위표, 지점 상세)이 함께 보는 '공용 상태 보관함'입니다.
//   예) 가중치 패널에서 슬라이더를 움직이면 weights가 바뀌고 → 지도 색과 순위표가 그 값을 보고 다시 계산됩니다.
//   zustand라는 작은 도구로 만들었고, 부품에서는 useAppStore((s) => s.weights)처럼 필요한 값만 꺼내 씁니다.
//   set(...)은 상태를 바꾸는 함수입니다. 배열·Set은 '새로 만들어서' 바꿔야 화면이 변화를 알아챕니다.
"use client";

import { create } from "zustand";

interface AppState {
  defaults: number[];          // 기본 가중치 8개 (rules.json에서 받음, '초기화' 버튼용)
  weights: number[];           // 현재 가중치 8개 (슬라이더 값)
  selected: boolean[];         // 위험요인 8개 켜짐/꺼짐
  gradeFilter: Set<string>;    // 지도에 보일 등급 (예: {"낮음","주의","높음"})
  selectedKey: string | null;  // 지금 상세를 열어 둔 지점의 key (없으면 null)
  showChanges: boolean;        // '최근 추가·삭제' 레이어 표시 여부
  initRules: (defaults: number[], grades: string[]) => void;   // 처음 한 번 기본값 채우기
  setWeight: (i: number, w: number) => void;                  // i번째 가중치를 w로
  toggleRule: (i: number) => void;                            // i번째 요인 켜기/끄기
  resetWeights: () => void;                                   // 가중치·켜짐 상태를 기본값으로
  toggleGrade: (label: string) => void;                       // 등급 필터 켜기/끄기
  selectPoint: (key: string | null) => void;                  // 지점 선택(상세 열기/닫기)
  setShowChanges: (v: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  defaults: [],
  weights: [],
  selected: [],
  gradeFilter: new Set(),
  selectedKey: null,
  showChanges: false,
  // 이미 채워져 있으면(다른 화면에 갔다 와도) 사용자가 바꾼 값을 지우지 않고 그대로 둔다
  initRules: (defaults, grades) =>
    set((s) => (s.defaults.length ? s : {
      defaults, weights: [...defaults], selected: defaults.map(() => true), gradeFilter: new Set(grades),
    })),
  setWeight: (i, w) => set((s) => ({ weights: s.weights.map((x, j) => (j === i ? w : x)) })),
  toggleRule: (i) => set((s) => ({ selected: s.selected.map((x, j) => (j === i ? !x : x)) })),
  resetWeights: () => set((s) => ({ weights: [...s.defaults], selected: s.defaults.map(() => true) })),
  toggleGrade: (label) => set((s) => {
    const g = new Set(s.gradeFilter);
    if (g.has(label)) g.delete(label);
    else g.add(label);
    return { gradeFilter: g };
  }),
  selectPoint: (key) => set({ selectedKey: key }),
  setShowChanges: (v) => set({ showChanges: v }),
}));
