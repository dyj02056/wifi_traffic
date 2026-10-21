// 카카오 주소·장소 검색 (지도와 같은 JavaScript 키, services 라이브러리). 와이파이 지점이 아니라 "그 위치로 이동"용.
//
// [이 파일이 하는 일]
//   검색창에 "화정역"이나 "고양시 덕양구 ○○로" 같은 장소·주소를 치면 카카오에 물어 좌표를 받아 옵니다.
//   주소 검색(Geocoder)과 장소 이름 검색(Places)을 동시에 하고, 같은 이름은 하나만 남겨 limit개까지 돌려줍니다.
//   (와이파이 지점 검색은 api.ts의 searchPoints가 따로 한다)
"use client";

import { loadSdk } from "@/components/KakaoMap";
import { config } from "./config";

// 검색 결과 한 건: label(큰 글씨 이름), sub(작은 글씨 주소), 좌표
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
  // 카카오 검색 함수는 결과를 '콜백'(끝나면 불러 주는 함수)으로 주므로, await로 기다릴 수 있게 Promise로 감싼다
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
