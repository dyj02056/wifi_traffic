"use client";
// 카카오맵 (docs/requests.md #31). web-draft/js/map-kakao.js와 같은 방식:
// 마커는 CustomOverlay + div(.kmarker)라서 등급 색 변화가 CSS transition(0.4초)으로 부드럽게 바뀐다.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { config } from "@/lib/config";

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window { kakao?: any }
}

export interface MapPoint { key: string; name: string; lat: number; lng: number }
export interface MapChange { key: string; change: "added" | "removed"; snapshot_from: string; snapshot_to: string;
  place_name: string | null; lat: number; lng: number }

interface Props {
  points: MapPoint[];
  bbox: [number, number, number, number] | null;
  colorOf: (key: string) => string;
  /** 등급 단계 — 마커 안 기호(✓ ! ×)와 크기에 쓴다 */
  levelOf: (key: string) => "low" | "mid" | "high" | "";
  visibleOf: (key: string) => boolean;
  colorVersion: unknown;               // 바뀌면 다시 칠한다(가중치·필터 변경)
  selectedKey: string | null;
  changes: MapChange[];
  showChanges: boolean;
  onSelect: (key: string) => void;
  onViewChange: (contains: (lat: number, lng: number) => boolean) => void;
  /** 검색 등으로 이 좌표로 이동·확대 (seq가 바뀔 때마다) */
  focus?: { lat: number; lng: number; level: number; seq: number } | null;
}

function paint(ms: Map<string, { el: HTMLDivElement }>, colorOf: (k: string) => string,
  levelOf: (k: string) => string, visibleOf: (k: string) => boolean) {
  for (const [key, { el }] of ms) {
    el.style.background = colorOf(key);
    el.dataset.level = levelOf(key);
    el.classList.toggle("hidden-marker", !visibleOf(key));
  }
}

let sdkPromise: Promise<void> | null = null;
export function loadSdk(appKey: string) {
  sdkPromise ??= new Promise<void>((resolve, reject) => {
    const el = document.createElement("script");
    el.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(appKey)}&autoload=false&libraries=services`;
    el.onload = () => (window.kakao?.maps ? window.kakao.maps.load(() => resolve()) : reject(new Error("카카오맵 SDK 초기화 실패")));
    el.onerror = () => { sdkPromise = null; reject(new Error("카카오맵 SDK를 불러오지 못했습니다(인터넷 연결·앱 키·도메인 등록 확인).")); };
    document.head.append(el);
  });
  return sdkPromise;
}

export function KakaoMap(p: Props) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markers = useRef(new Map<string, { overlay: any; el: HTMLDivElement; pos: any }>());
  const ring = useRef<any>(null);
  const changeOverlays = useRef<any[]>([]);
  const cb = useRef(p);
  useLayoutEffect(() => { cb.current = p; });
  const [error, setError] = useState(config.kakaoJsKey ? "" : "no-key");
  const [ready, setReady] = useState(false);

  // 지도 만들기
  useEffect(() => {
    if (!config.kakaoJsKey) return;
    let ro: ResizeObserver | undefined;
    loadSdk(config.kakaoJsKey).then(() => {
      const k = window.kakao.maps;
      if (!elRef.current || mapRef.current) return;
      const map = new k.Map(elRef.current, { center: new k.LatLng(36.4, 127.8), level: 13 });
      map.addControl(new k.ZoomControl(), k.ControlPosition.LEFT);
      k.event.addListener(map, "idle", () => {
        const b = map.getBounds();
        cb.current.onViewChange((lat, lng) => b.contain(new k.LatLng(lat, lng)));
      });
      ro = new ResizeObserver(() => map.relayout());
      ro.observe(elRef.current);
      mapRef.current = map;
      setReady(true);
    }).catch((e) => setError(e.message));
    return () => ro?.disconnect();
  }, []);

  // 지역이 바뀌면 마커를 다시 그리고 그 지역으로 이동
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const k = window.kakao.maps;
    for (const { overlay } of markers.current.values()) overlay.setMap(null);
    markers.current.clear();
    for (const pt of p.points) {
      const el = document.createElement("div");
      el.className = "kmarker";
      el.style.background = cb.current.colorOf(pt.key);
      el.dataset.level = cb.current.levelOf(pt.key);
      el.dataset.name = pt.name;
      el.addEventListener("click", () => cb.current.onSelect(pt.key));
      const pos = new k.LatLng(pt.lat, pt.lng);
      const overlay = new k.CustomOverlay({ content: el, position: pos, xAnchor: 0.5, yAnchor: 0.5, zIndex: 2, clickable: true });
      overlay.setMap(map);
      markers.current.set(pt.key, { overlay, el, pos });
    }
    if (!p.bbox) return;
    const [w, s, e, n] = p.bbox;
    const fit = () => {
      map.relayout();
      map.setBounds(new k.LatLngBounds(new k.LatLng(s, w), new k.LatLng(n, e)), 24, 24, 24, 24);
    };
    const box = elRef.current!;
    // 지도 영역 크기가 0이면(숨김 상태 등) 크기가 생긴 뒤에 맞춘다 (web-draft map.js와 같은 방어)
    if (box.clientWidth && box.clientHeight) fit();
    else {
      const once = new ResizeObserver(() => {
        if (box.clientWidth && box.clientHeight) { once.disconnect(); fit(); }
      });
      once.observe(box);
      return () => once.disconnect();
    }
  }, [ready, p.points, p.bbox]);

  // 색·필터 다시 칠하기
  useEffect(() => {
    paint(markers.current, cb.current.colorOf, cb.current.levelOf, cb.current.visibleOf);
  }, [p.colorVersion, p.points]);

  // 선택 지점 링
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    ring.current?.setMap(null);
    ring.current = null;
    const m = p.selectedKey ? markers.current.get(p.selectedKey) : null;
    if (!m) return;
    const el = document.createElement("div");
    el.className = "kmarker-ring";
    ring.current = new window.kakao.maps.CustomOverlay({ content: el, position: m.pos, xAnchor: 0.5, yAnchor: 0.5, zIndex: 3 });
    ring.current.setMap(map);
    map.panTo(m.pos);
  }, [ready, p.selectedKey, p.points]);

  // 검색으로 고른 위치로 이동·확대 (지역 이동 setBounds가 끝난 뒤에 적용되도록 다음 프레임에)
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !p.focus) return;
    const { lat, lng, level } = p.focus;
    const t = setTimeout(() => {
      map.setLevel(level);
      map.setCenter(new window.kakao.maps.LatLng(lat, lng));
    }, 50);
    return () => clearTimeout(t);
  }, [ready, p.focus, p.points]);

  // 추가·삭제 레이어
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const k = window.kakao.maps;
    for (const o of changeOverlays.current) o.setMap(null);
    changeOverlays.current = p.changes.map((c) => {
      const added = c.change === "added";
      const el = document.createElement("div");
      el.className = `kchange ${added ? "added" : "removed"}`;
      el.dataset.name = `${added ? "추가" : "삭제"} (${c.snapshot_from} → ${c.snapshot_to}): ${c.place_name ?? ""}`;
      const o = new k.CustomOverlay({ content: el, position: new k.LatLng(c.lat, c.lng), xAnchor: 0.5, yAnchor: 0.5, zIndex: 1 });
      if (p.showChanges) o.setMap(map);
      return o;
    });
  }, [ready, p.changes, p.showChanges]);

  if (error === "no-key") {
    return (
      <div className="map-placeholder">
        <div>
          카카오맵 키가 없어 지도를 그리지 않습니다.<br />
          <code>frontend/.env.local</code>에 <code>NEXT_PUBLIC_KAKAO_JS_KEY</code>를 넣고,<br />
          카카오 개발자 콘솔 [플랫폼 &gt; Web]에 이 주소(<code>{typeof window !== "undefined" ? location.origin : ""}</code>)를 등록하세요.<br />
          지역 선택·가중치·순위표·지점 상세는 지도 없이도 동작합니다.
        </div>
      </div>
    );
  }
  return (
    <>
      <div ref={elRef} className="map-canvas" />
      {error && <div className="map-placeholder"><div>{error}</div></div>}
    </>
  );
}
