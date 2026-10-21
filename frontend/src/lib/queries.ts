// TanStack Query 훅 — 번들 문서는 하루 1회 갱신이라 화면 안에서는 다시 받지 않는다.
//
// [이 파일이 하는 일]
//   화면 부품(컴포넌트)이 데이터를 쉽게 쓰도록 'use○○' 모양의 함수(훅)를 제공합니다.
//   예) const { data, isLoading, error } = usePoints("41-goyang")
//   TanStack Query라는 도구가 받아 온 데이터를 기억(캐시)해 두어, 여러 화면에서 같은 데이터를 요청해도 한 번만 받습니다.
//   queryKey는 데이터를 구별하는 이름표입니다. enabled: !!rid 는 "지역이 정해졌을 때만 받기"라는 뜻입니다.
//   (훅: 이름이 use로 시작하는 React 전용 함수. 컴포넌트 안에서 상태나 데이터를 쓸 때 부른다)
"use client";

import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "./api";
import { config } from "./config";

// 백업에 없는 지역(ApiUnavailableError)은 다시 시도해도 같으므로 바로 오류로 보여 준다("다시 시도"는 화면에서)
// staleTime·gcTime: Infinity = 한 번 받은 데이터는 페이지를 새로 열기 전까지 계속 쓴다
// retry: 실패하면 한 번만 다시 시도(백업에 없는 지역 오류는 다시 시도하지 않음)
const once = {
  staleTime: Infinity, gcTime: Infinity,
  retry: (n: number, e: Error) => n < 1 && !api.isApiUnavailable(e),
} as const;

export const useMeta = () => useQuery({ queryKey: ["meta"], queryFn: api.getMeta, ...once });
export const useRules = () => useQuery({ queryKey: ["rules"], queryFn: api.getRules, ...once });
export const useRegions = () => useQuery({ queryKey: ["regions"], queryFn: api.getRegions, ...once });
export const usePoints = (rid: string | null) =>
  useQuery({ queryKey: ["points", rid], queryFn: () => api.getPoints(rid!), enabled: !!rid, ...once });
export const useChanges = (rid: string | null) =>
  useQuery({ queryKey: ["changes", rid], queryFn: () => api.getChanges(rid!), enabled: !!rid, ...once });
export const useSensitivity = (rid: string | null) =>
  useQuery({ queryKey: ["sensitivity", rid], queryFn: () => api.getSensitivity(rid!), enabled: !!rid, ...once });
export const useDetail = (key: string | null) =>
  useQuery({ queryKey: ["detail", key], queryFn: () => api.getDetail(key!), enabled: !!key, ...once });
export const useBackground = () => useQuery({ queryKey: ["background"], queryFn: api.getBackground, ...once });
export const useCases = () => useQuery({ queryKey: ["cases"], queryFn: api.getCases, ...once });

/** 지금 데이터를 어디서 받고 있는지(API / 정적 백업) */
export function useDataSource(): api.DataSource {
  return useSyncExternalStore((fn) => { const off = api.onDataSourceChange(fn); return () => { off(); }; },
    api.dataSource, () => (config.apiBase ? "api" : "static"));
}

// 사용자가 운영체제에서 '움직임 줄이기'를 켰는지 알려 주는 훅(켜져 있으면 애니메이션을 생략한다).
// 설정이 바뀌면 화면도 바로 따라 바뀐다.
const RM = "(prefers-reduced-motion: reduce)";
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore((fn) => {
    const mq = matchMedia(RM);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, () => matchMedia(RM).matches, () => false);
}
