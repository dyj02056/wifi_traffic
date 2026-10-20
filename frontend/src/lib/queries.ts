// TanStack Query 훅 — 번들 문서는 하루 1회 갱신이라 화면 안에서는 다시 받지 않는다.
"use client";

import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "./api";
import { config } from "./config";

const once = { staleTime: Infinity, gcTime: Infinity, retry: 1 } as const;

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

const RM = "(prefers-reduced-motion: reduce)";
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore((fn) => {
    const mq = matchMedia(RM);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, () => matchMedia(RM).matches, () => false);
}
