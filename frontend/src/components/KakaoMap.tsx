"use client";
// 카카오맵 (docs/requests.md #31). web-draft/js/map-kakao.js와 같은 방식:
// 마커는 CustomOverlay + div(.kmarker)라서 등급 색 변화가 CSS transition(0.4초)으로 부드럽게 바뀐다.
// 움직임: 처음 나타날 때 톡 튀어나옴, 주의·높음은 파동(.kpulse)이 퍼짐, 등급이 바뀌면 한 번 튐(.kbump).
//
// [이 파일이 하는 일]
//   카카오맵을 화면에 띄우고, 그 위에 와이파이 지점마다 신호등 색 마커(낮음 ✓ / 주의 ! / 높음 ×)를 그립니다.
//   그 밖에 선택 지점 고리, 검색 위치로 이동, '내 위치' 보라색 핀, 최근 추가·삭제 표시도 맡습니다.
//   React 부품이지만 지도 위 마커는 카카오 SDK가 직접 관리하는 HTML 요소라서,
//   useEffect 안에서 "무엇이 바뀌면 지도에 무엇을 다시 그릴지"를 하나씩 나눠 처리합니다.
//   (SDK: 카카오가 제공하는 지도 프로그램 묶음. 인터넷에서 불러와야 쓸 수 있다)
//   useRef: 화면을 다시 그려도 사라지지 않는 보관 상자. 지도·마커 객체를 여기에 담아 둔다.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { config } from "@/lib/config";
import { fmt } from "./format";

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window { kakao?: any }
}

// 지도에 찍을 지점 한 곳, 그리고 최근 추가·삭제된 지점 한 곳의 모양
export interface MapPoint { key: string; name: string; lat: number; lng: number }
export interface MapChange { key: string; change: "added" | "removed"; snapshot_from: string; snapshot_to: string;
  place_name: string | null; lat: number; lng: number }

// 이 부품이 받는 값들 (MapScreen.tsx가 넘겨준다)
interface Props {
  points: MapPoint[];
  /** 처음 보여 줄 범위 [서, 남, 동, 북] */
  bbox: [number, number, number, number] | null;
  /** 지점 key → 마커 색 (현재 가중치로 다시 계산한 등급의 색) */
  colorOf: (key: string) => string;
  /** 등급 단계 — 마커 안 기호(✓ ! ×)와 크기에 쓴다 */
  levelOf: (key: string) => "low" | "mid" | "high" | "";
  /** 같은 좌표에 겹친 지점 중 대표(가장 위험한 곳)를 고를 때 쓴다 — 높을수록 위험 */
  scoreOf: (key: string) => number | null;
  /** 등급 필터에 걸려 숨겨야 하면 false */
  visibleOf: (key: string) => boolean;
  colorVersion: unknown;               // 바뀌면 다시 칠한다(가중치·필터 변경)
  selectedKey: string | null;
  changes: MapChange[];
  showChanges: boolean;
  /** 마커를 눌렀을 때 */
  onSelect: (key: string) => void;
  /** 지도를 움직일 때마다 '이 좌표가 지금 화면 안에 있나' 판별 함수를 넘겨준다(화면 안 추천 TOP 3용) */
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
interface Group { keys: string[]; name: string; el: HTMLDivElement; score: HTMLElement; overlay: any; pos: any }

// 묶음(같은 좌표의 지점들) 중 마커에 대표로 보여 줄 지점을 고른다
function pickRep(keys: string[], p: Pick<Props, "scoreOf" | "visibleOf">, selectedKey: string | null) {
  if (selectedKey && keys.includes(selectedKey)) return selectedKey;
  const vis = keys.filter(p.visibleOf);
  return (vis.length ? vis : keys).reduce((a, b) => ((p.scoreOf(b) ?? -Infinity) > (p.scoreOf(a) ?? -Infinity) ? b : a));
}

// 모든 마커의 색·등급 기호·이름표 점수·숨김 여부를 지금 값으로 다시 칠한다(마커를 새로 만들지 않아 빠르다)
function paint(gs: Map<string, Group>, p: Props) {
  for (const g of gs.values()) {
    const { el } = g;
    const key = pickRep(g.keys, p, p.selectedKey);
    const vis = g.keys.filter(p.visibleOf);
    const shown = vis.length;
    el.dataset.key = key;
    // 이름표: 이름 + 그 자리에서 가장 높은 점수(그 점수의 등급 색)
    const top = pickRep(g.keys, p, null);
    const ts = p.scoreOf(top);
    g.score.textContent = ts != null ? fmt(ts) : "";
    g.score.style.color = p.colorOf(top);
    el.style.background = p.colorOf(key);
    const level = p.levelOf(key);
    // 등급이 바뀐 마커만 한 번 튀어 오르게 (애니메이션 다시 시작)
    if (el.dataset.level && el.dataset.level !== level) {
      el.classList.remove("kbump");
      // offsetWidth를 읽으면 브라우저가 화면을 한 번 계산한다 → 같은 애니메이션 클래스를 다시 붙여도 처음부터 재생된다
      void el.offsetWidth;
      el.classList.add("kbump");
    }
    el.dataset.level = level;
    el.classList.toggle("hidden-marker", !shown);
  }
}

// 카카오맵 SDK를 한 번만 불러온다(여러 곳에서 불러도 같은 Promise를 공유). 실패하면 다음에 다시 시도할 수 있게 비운다.
// libraries=services: 주소·장소 검색 기능도 함께 불러온다(lib/geo.ts에서 사용)
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
  // 지도 이벤트(클릭 등)는 한 번만 등록하므로, 항상 최신 props를 보도록 cb에 담아 매번 갱신한다
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
      // 처음에는 한반도 가운데(위도 36.4, 경도 127.8)를 넓게(level 13) 보여 준다. level은 클수록 넓게 보인다
      const map = new k.Map(elRef.current, { center: new k.LatLng(36.4, 127.8), level: 13 });
      map.addControl(new k.ZoomControl(), k.ControlPosition.LEFT);
      k.event.addListener(map, "click", (e: any) => {
        if (cb.current.picking) cb.current.onPick?.(e.latLng.getLat(), e.latLng.getLng());
      });
      // idle: 지도 이동·확대가 끝났을 때
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
      // 좌표 글자를 묶음 이름으로 쓴다. 같은 좌표의 두 번째 지점부터는 기존 묶음에 key만 추가
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
      // 이름표(마우스를 올리면 보임): 이름 + 등급 색 점수. 점수만 색을 달리하려고 ::after 대신 실제 요소로 둔다
      const label = document.createElement("span");
      label.className = "klabel";
      const score = document.createElement("b");
      label.append(pt.name, " ", score);
      el.append(pulse, label);
      // 누르면 지금 지도에 보이는 대표 지점을 고른다(같은 장소의 다른 AP는 상세에서 바꿔 볼 수 있다)
      el.addEventListener("click", () => (cb.current.picking ? cb.current.onPick?.(pt.lat, pt.lng) : cb.current.onSelect(el.dataset.key!)));
      const pos = new k.LatLng(pt.lat, pt.lng);
      const overlay = new k.CustomOverlay({ content: el, position: pos, xAnchor: 0.5, yAnchor: 0.5, zIndex: 2, clickable: true });
      overlay.setMap(map);
      // 마우스를 올린 마커를 맨 위로 — 이웃 마커가 이름표를 덮지 않게
      el.addEventListener("mouseenter", () => overlay.setZIndex(5));
      el.addEventListener("mouseleave", () => overlay.setZIndex(2));
      markers.current.set(gid, { keys: [pt.key], name: pt.name, el, score, overlay, pos });
    }
    paint(markers.current, cb.current);
    // 지역 범위(bbox)가 화면에 꽉 차도록 맞춘다(가장자리 여백 24px)
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

  // 지도 키가 없으면 지도 대신 설정 안내를 보여 준다(나머지 기능은 지도 없이도 동작)
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
