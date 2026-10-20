// 카카오맵: map.js(Leaflet)와 같은 함수 이름·동작. 마커는 CustomOverlay + div(css .kmarker)로 그려 색 전환을 CSS transition으로 한다.
/* global kakao */

let map, highlight;
const markers = new Map();   // key -> { overlay, el, pos }
let changeOverlays = [];
let changesVisible = false;
let onSelect = () => {};

export function loadSdk(appKey) {
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(appKey)}&autoload=false`;
    el.onload = () => (window.kakao?.maps ? kakao.maps.load(resolve) : reject(new Error("카카오맵 SDK 초기화 실패")));
    el.onerror = () => reject(new Error("카카오맵 SDK를 불러오지 못했습니다(인터넷 연결·앱 키 확인)."));
    document.head.append(el);
  });
}

const latlng = (lat, lng) => new kakao.maps.LatLng(lat, lng);

function overlay(el, pos, z = 1) {
  return new kakao.maps.CustomOverlay({ content: el, position: pos, xAnchor: 0.5, yAnchor: 0.5, zIndex: z, clickable: true });
}

export function initMap(el, { onPointClick }) {
  onSelect = onPointClick;
  map = new kakao.maps.Map(el, { center: latlng(36.4, 127.8), level: 13 });
  map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.LEFT);
  // 사이드 시트가 열리고 닫혀 지도 크기가 바뀌면 다시 맞춘다
  new ResizeObserver(() => map.relayout()).observe(el);
  return map;
}

export function showPoints(points, colorOf, bbox) {
  for (const { overlay: o } of markers.values()) o.setMap(null);
  markers.clear();
  for (const p of points) {
    const el = document.createElement("div");
    el.className = "kmarker";
    el.style.background = colorOf(p.key);
    el.dataset.name = p.name;
    el.addEventListener("click", () => onSelect(p.key));
    const pos = latlng(p.lat, p.lng);
    const o = overlay(el, pos, 2);
    o.setMap(map);
    markers.set(p.key, { overlay: o, el, pos });
  }
  if (bbox) {
    map.relayout();
    const [w, s, e, n] = bbox;
    map.setBounds(new kakao.maps.LatLngBounds(latlng(s, w), latlng(n, e)), 24, 24, 24, 24);
  }
}

export function recolor(colorOf, visibleOf) {
  for (const [key, { el }] of markers) {
    const visible = visibleOf(key);
    el.style.background = colorOf(key);
    el.classList.toggle("hidden-marker", !visible);
  }
}

export function select(key) {
  clearSelection();
  const m = markers.get(key);
  if (!m) return;
  const el = document.createElement("div");
  el.className = "kmarker-ring";
  highlight = new kakao.maps.CustomOverlay({ content: el, position: m.pos, xAnchor: 0.5, yAnchor: 0.5, zIndex: 3 });
  highlight.setMap(map);
  map.panTo(m.pos);
}

export function clearSelection() {
  if (highlight) { highlight.setMap(null); highlight = null; }
}

export function showChanges(changes, visible) {
  for (const o of changeOverlays) o.setMap(null);
  changeOverlays = changes.map((c) => {
    const added = c.change === "added";
    const el = document.createElement("div");
    el.className = `kchange ${added ? "added" : "removed"}`;
    el.dataset.name = `${added ? "추가" : "삭제"} (${c.snapshot_from} → ${c.snapshot_to}): ${c.place_name ?? ""}`;
    return overlay(el, latlng(c.lat, c.lng), 1);
  });
  setChangesVisible(visible);
}

export function onViewChange(cb) {
  kakao.maps.event.addListener(map, "idle", cb);
}

export function contains(lat, lng) {
  return map.getBounds().contain(latlng(lat, lng));
}

export function setChangesVisible(visible) {
  changesVisible = visible;
  for (const o of changeOverlays) o.setMap(changesVisible ? map : null);
}
