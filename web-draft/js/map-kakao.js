// 카카오맵: map.js(Leaflet)와 같은 함수 이름·동작. 마커는 CustomOverlay + div(css .kmarker)로 그려 색 전환을 CSS transition으로 한다.
//
// [이 파일이 하는 일]
//   카카오맵 키가 있을 때 쓰는 지도입니다. 지점 마커, 선택 고리, 추가·삭제 표시를 카카오맵 위에 그립니다.
//   CustomOverlay: 카카오맵 위 원하는 좌표에 직접 만든 HTML 조각을 올려놓는 기능.
//   그래서 마커 색을 CSS로 바꿀 수 있고, 색이 바뀔 때 0.4초 동안 부드럽게 변하는 효과를 낼 수 있다.
/* global kakao */

let map, highlight;
const markers = new Map();   // key -> { overlay, el, pos }
let changeOverlays = [];
let changesVisible = false;
let onSelect = () => {};

// 카카오맵 SDK(지도 프로그램)를 인터넷에서 불러온다. autoload=false라서 불러온 뒤 kakao.maps.load로 준비를 마친다
export function loadSdk(appKey) {
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(appKey)}&autoload=false`;
    el.onload = () => (window.kakao?.maps ? kakao.maps.load(resolve) : reject(new Error("카카오맵 SDK 초기화 실패")));
    el.onerror = () => reject(new Error("카카오맵 SDK를 불러오지 못했습니다(인터넷 연결·앱 키 확인)."));
    document.head.append(el);
  });
}

// 좌표 객체 만들기, HTML 조각을 좌표 위에 올리는 오버레이 만들기(z: 겹칠 때 위에 오는 순서)
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

// 지점 마커를 모두 새로 그리고(기존 마커는 지도에서 뗀다), 지역 범위로 화면을 맞춘다
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

// 마커 색 다시 칠하기. 등급 필터에 걸린 마커는 hidden-marker 클래스로 숨긴다
export function recolor(colorOf, visibleOf) {
  for (const [key, { el }] of markers) {
    const visible = visibleOf(key);
    el.style.background = colorOf(key);
    el.classList.toggle("hidden-marker", !visible);
  }
}

// 선택한 지점에 고리를 두르고 지도 가운데로 옮긴다
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

// 최근 추가·삭제 표시를 만든다(보일지는 visible로 정함)
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

// 지도 이동·확대가 끝날 때(idle)마다 cb 호출 (추천 TOP 3 갱신용)
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
