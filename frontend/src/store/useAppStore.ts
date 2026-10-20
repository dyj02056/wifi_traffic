// 지도 화면 상태: 가중치·선택 규칙·등급 필터·선택 지점·레이어 (plan.md §9.1)
"use client";

import { create } from "zustand";

interface AppState {
  defaults: number[];
  weights: number[];
  selected: boolean[];
  gradeFilter: Set<string>;
  selectedKey: string | null;
  showChanges: boolean;
  initRules: (defaults: number[], grades: string[]) => void;
  setWeight: (i: number, w: number) => void;
  toggleRule: (i: number) => void;
  resetWeights: () => void;
  toggleGrade: (label: string) => void;
  selectPoint: (key: string | null) => void;
  setShowChanges: (v: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  defaults: [],
  weights: [],
  selected: [],
  gradeFilter: new Set(),
  selectedKey: null,
  showChanges: false,
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
