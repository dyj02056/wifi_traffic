// 카카오 주소·장소 검색 (지도와 같은 JavaScript 키, services 라이브러리). 와이파이 지점이 아니라 "그 위치로 이동"용.
"use client";

import { loadSdk } from "@/components/KakaoMap";
import { config } from "./config";

export interface Place { label: string; sub: string; lat: number; lng: number }

/* eslint-disable @typescript-eslint/no-explicit-any */
export async function searchPlaces(q: string, limit = 3): Promise<Place[]> {
  if (!config.kakaoJsKey || !q.trim()) return [];
  try {
    await loadSdk(config.kakaoJsKey);
  } catch {
    return [];
  }
  const svc = window.kakao?.maps?.services;
  if (!svc) return [];
  const call = (fn: (cb: (res: any[], status: string) => void) => void) =>
    new Promise<any[]>((resolve) => fn((res, status) => resolve(status === svc.Status.OK ? res : [])));
  const [addr, kw] = await Promise.all([
    call((cb) => new svc.Geocoder().addressSearch(q, cb)),
    call((cb) => new svc.Places().keywordSearch(q, cb, { size: limit })),
  ]);
  const out: Place[] = [
    ...addr.map((a) => ({ label: a.address_name, sub: a.road_address?.address_name ?? "주소", lat: +a.y, lng: +a.x })),
    ...kw.map((k) => ({ label: k.place_name, sub: k.road_address_name || k.address_name, lat: +k.y, lng: +k.x })),
  ];
  const seen = new Set<string>();
  return out.filter((p) => !seen.has(p.label) && seen.add(p.label)).slice(0, limit);
}
