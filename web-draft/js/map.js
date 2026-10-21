// Leaflet 지도: 등급 색 마커, 선택 하이라이트, 추가·삭제 레이어. 색 전환은 CSS transition(main.css).
//
// [이 파일이 하는 일]
//   카카오맵 키가 없거나 불러오지 못했을 때 쓰는 '대체 지도'입니다. Leaflet(무료 지도 그리기 도구)에
//   오픈스트리트맵 그림(타일)을 깔고, 지점마다 등급 색 동그라미를 찍습니다.
//   map-kakao.js와 함수 이름·동작이 똑같아서 main.js는 어느 지도인지 신경 쓰지 않고 같은 방식으로 부릅니다.
//   (레이어: 지도 위에 겹쳐 올리는 투명한 판. 지점 판과 추가·삭제 판을 따로 둬서 하나만 켜고 끌 수 있다)
/* global L */

let map, pointLayer, changeLayer, highlight;
const markers = new Map();   // key -> circleMarker
let onSelect = () => {};

// 지도를 만든다. 처음에는 한반도 가운데(위도 36.4, 경도 127.8)를 확대 수준 7로 보여 준다
export function initMap(el, { onPointClick }) {
  onSelect = onPointClick;
  map = L.map(el, { preferCanvas: false, zoomControl: true }).setView([36.4, 127.8], 7);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  pointLayer = L.layerGroup().addTo(map);
  changeLayer = L.layerGroup();
  return map;
}

// 지점 마커를 모두 새로 찍고, 지역 범위(bbox)로 화면을 옮긴다('움직임 줄이기' 설정이면 날아가는 효과 없이)
export function showPoints(points, colorOf, bbox) {
  pointLayer.clearLayers();
  markers.clear();
  for (const p of points) {
    const m = L.circleMarker([p.lat, p.lng], {
      radius: 11, weight: 2.5, color: "#ffffff", fillColor: colorOf(p.key), fillOpacity: 0.95,
    });
    m.bindTooltip(p.name, { direction: "top" });
    m.on("click", () => onSelect(p.key));
    m.addTo(pointLayer);
    markers.set(p.key, m);
  }
  if (bbox) {
    map.invalidateSize();
    const [w, s, e, n] = bbox;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const bounds = L.latLngBounds([s, w], [n, e]).pad(0.05);
    const size = map.getSize();
    // 지도 영역 크기가 0이면(백그라운드 탭에서 열림 등) flyToBounds가 0으로 나눠 NaN 오류를 낸다.
    // 중심만 옮겨 두고, 크기가 생기면(resize) 그때 영역에 맞춘다.
    if (!size.x || !size.y) {
      map.setView(bounds.getCenter(), map.getZoom(), { animate: false });
      map.once("resize", () => map.fitBounds(bounds));
    } else if (reduce) map.fitBounds(bounds);
    else map.flyToBounds(bounds, { duration: 1.2 });
  }
}

// 마커 색만 다시 칠한다. 등급 필터에 걸린 마커는 투명하게 하고 클릭도 안 되게 한다
export function recolor(colorOf, visibleOf) {
  for (const [key, m] of markers) {
    const visible = visibleOf(key);
    m.setStyle({ fillColor: colorOf(key), fillOpacity: visible ? 0.95 : 0, opacity: visible ? 1 : 0 });
    if (m._path) m._path.style.pointerEvents = visible ? "" : "none";
  }
}

// 선택한 지점에 흰 고리를 두르고 지도 가운데로 옮긴다 / 고리 지우기
export function select(key) {
  if (highlight) { highlight.remove(); highlight = null; }
  const m = markers.get(key);
  if (!m) return;
  highlight = L.circleMarker(m.getLatLng(), {
    radius: 18, weight: 4, color: "#ffffff", fill: false, interactive: false,
  }).addTo(map);
  map.panTo(m.getLatLng());
}

export function clearSelection() {
  if (highlight) { highlight.remove(); highlight = null; }
}

// 최근 추가(초록 실선 고리)·삭제(회색 점선 고리) 지점을 그린다
export function showChanges(changes, visible) {
  changeLayer.clearLayers();
  for (const c of changes) {
    const added = c.change === "added";
    L.circleMarker([c.lat, c.lng], {
      radius: 16, weight: 3, fill: false, interactive: true,
      color: added ? getComputedStyle(document.documentElement).getPropertyValue("--added").trim() : "#6b7280",
      dashArray: added ? null : "4 4",
    }).bindTooltip(`${added ? "추가" : "삭제"} (${c.snapshot_from} → ${c.snapshot_to}): ${c.place_name ?? ""}`)
      .addTo(changeLayer);
  }
  setChangesVisible(visible);
}

// 지도 이동·확대가 끝날 때마다 cb 호출 (추천 TOP 3 갱신용)
export function onViewChange(cb) {
  map.on("moveend", cb);
}

// 그 좌표가 지금 지도 화면 안에 있는지
export function contains(lat, lng) {
  return map.getBounds().contains([lat, lng]);
}

// 추가·삭제 레이어 켜기/끄기
export function setChangesVisible(visible) {
  if (visible) changeLayer.addTo(map);
  else changeLayer.remove();
}
