"use client";
// 카카오맵 (docs/requests.md #31). web-draft/js/map-kakao.js와 같은 방식:
// 마커는 CustomOverlay + div(.kmarker)라서 등급 색 변화가 CSS transition(0.4초)으로 부드럽게 바뀐다.
// 움직임: 처음 나타날 때 톡 튀어나옴, 주의·높음은 파동(.kpulse)이 퍼짐, 등급이 바뀌면 한 번 튐(.kbump).

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
  /** 같은 좌표에 겹친 지점 중 대표(가장 위험한 곳)를 고를 때 쓴다 — 높을수록 위험 */
  scoreOf: (key: string) => number | null;
  visibleOf: (key: string) => boolean;
  colorVersion: unknown;               // 바뀌면 다시 칠한다(가중치·필터 변경)
  selectedKey: string | null;
  changes: MapChange[];
  showChanges: boolean;
  onSelect: (key: string) => void;
  onViewChange: (contains: (lat: number, lng: number) => boolean) => void;
  /** 검색 등으로 이 좌표로 이동·확대 (seq가 바뀔 때마다) */
  focus?: { lat: number; lng: number; level: number; seq: number } | null;
  /** 사용자가 지도에서 직접 찍은 내 위치 — 지점 마커와 구분되는 보라색 핀 */
  myLocation?: { lat: number; lng: number } | null;
  /** true면 다음 클릭(지도·지점 마커 어디든)을 내 위치 지정으로 쓴다 */
  picking?: boolean;
  onPick?: (lat: number, lng: number) => void;
}

// 같은 좌표(한 건물의 보안·개방 SSID 등)는 마커 하나로 묶는다. 겹쳐 그리면 나중에 그린 마커가 덮어서
// 순위·상세의 점수와 지도 색이 어긋나 보였다. 대표: 선택한 지점이 있으면 그 지점, 없으면 보이는 것 중 가장 위험한 곳
interface Group { keys: string[]; name: string; el: HTMLDivElement; overlay: any; pos: any }

function pickRep(keys: string[], p: Pick<Props, "scoreOf" | "visibleOf">, selectedKey: string | null) {
  if (selectedKey && keys.includes(selectedKey)) return selectedKey;
  const vis = keys.filter(p.visibleOf);
  return (vis.length ? vis : keys).reduce((a, b) => ((p.scoreOf(b) ?? -Infinity) > (p.scoreOf(a) ?? -Infinity) ? b : a));
}

function paint(gs: Map<string, Group>, p: Props) {
  for (const g of gs.values()) {
    const { el } = g;
    const key = pickRep(g.keys, p, p.selectedKey);
    const shown = g.keys.filter(p.visibleOf).length;
    el.dataset.key = key;
    el.dataset.name = shown > 1 ? `${g.name} · 같은 장소 AP ${shown}대` : g.name;
    el.style.background = p.colorOf(key);
    const level = p.levelOf(key);
    // 등급이 바뀐 마커만 한 번 튀어 오르게 (애니메이션 다시 시작)
    if (el.dataset.level && el.dataset.level !== level) {
      el.classList.remove("kbump");
      void el.offsetWidth;
      el.classList.add("kbump");
    }
    el.dataset.level = level;
    el.classList.toggle("hidden-marker", !shown);
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
  const markers = useRef(new Map<string, Group>());      // 좌표 → 묶음
  const groupOf = useRef(new Map<string, string>());      // 지점 key → 좌표
  const ring = useRef<any>(null);
  const myLoc = useRef<any>(null);
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
      k.event.addListener(map, "click", (e: any) => {
        if (cb.current.picking) cb.current.onPick?.(e.latLng.getLat(), e.latLng.getLng());
      });
      k.event.addListener(map, "idle", () => {
        const b = map.getBounds();
        cb.current.onViewChange((lat, lng) => b.contain(new k.LatLng(lat, lng)));
      });
      // 옆 칸을 접고 펼쳐 지도 크기가 바뀌어도 보던 곳이 가운데에 남도록 중심을 지킨다
      ro = new ResizeObserver(() => { const c = map.getCenter(); map.relayout(); map.setCenter(c); });
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
    groupOf.current.clear();
    for (const pt of p.points) {
      const gid = `${pt.lat},${pt.lng}`;
      groupOf.current.set(pt.key, gid);
      const had = markers.current.get(gid);
      if (had) { had.keys.push(pt.key); continue; }
      const el = document.createElement("div");
      el.className = "kmarker";
      // 처음 그릴 때 하나씩 톡톡 나타나도록 시작 시간을 조금씩 흩는다
      el.style.animationDelay = `${Math.round(Math.random() * 600)}ms`;
      // 퍼지는 파동(주의·높음만 CSS에서 보임). ::before는 기호, ::after는 이름표라 따로 둔다
      const pulse = document.createElement("span");
      pulse.className = "kpulse";
      pulse.style.animationDelay = `${Math.round(Math.random() * 1800)}ms`;
      el.append(pulse);
      // 누르면 지금 지도에 보이는 대표 지점을 고른다(같은 장소의 다른 AP는 상세에서 바꿔 볼 수 있다)
      el.addEventListener("click", () => (cb.current.picking ? cb.current.onPick?.(pt.lat, pt.lng) : cb.current.onSelect(el.dataset.key!)));
      const pos = new k.LatLng(pt.lat, pt.lng);
      const overlay = new k.CustomOverlay({ content: el, position: pos, xAnchor: 0.5, yAnchor: 0.5, zIndex: 2, clickable: true });
      overlay.setMap(map);
      markers.current.set(gid, { keys: [pt.key], name: pt.name, el, overlay, pos });
    }
    paint(markers.current, cb.current);
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

  // 색·필터·선택 다시 칠하기 (선택하면 겹친 마커가 그 지점의 색으로 바뀐다)
  useEffect(() => {
    paint(markers.current, cb.current);
  }, [p.colorVersion, p.points, p.visibleOf, p.selectedKey]);

  // 선택 지점 링
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    ring.current?.setMap(null);
    ring.current = null;
    const gid = p.selectedKey ? groupOf.current.get(p.selectedKey) : undefined;
    const m = gid ? markers.current.get(gid) : null;
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

  // 내 위치: 핀('나')과 '내 위치' 이름표. 지점 마커(신호등 색)·선택 고리(파랑)와 겹치지 않게 보라색, 맨 위에 그린다
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    myLoc.current?.setMap(null);
    myLoc.current = null;
    if (!p.myLocation) return;
    const el = document.createElement("div");
    el.className = "kmyloc";
    el.innerHTML = '<span class="kmyloc-label">내 위치</span><span class="kmyloc-halo"></span><span class="kmyloc-pin"><b>나</b></span>';
    myLoc.current = new window.kakao.maps.CustomOverlay({ content: el, xAnchor: 0.5, yAnchor: 1, zIndex: 10,
      position: new window.kakao.maps.LatLng(p.myLocation.lat, p.myLocation.lng) });
    myLoc.current.setMap(map);
  }, [ready, p.myLocation]);

  // 내 위치 찍기 모드: 십자 커서
  useEffect(() => {
    if (ready) mapRef.current?.setCursor(p.picking ? "crosshair" : "");
  }, [ready, p.picking]);

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
