// Leaflet 지도: 등급 색 마커, 선택 하이라이트, 추가·삭제 레이어. 색 전환은 CSS transition(main.css).
/* global L */

let map, pointLayer, changeLayer, highlight;
const markers = new Map();   // key -> circleMarker
let onSelect = () => {};

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
    if (reduce) map.fitBounds(bounds);
    else map.flyToBounds(bounds, { duration: 1.2 });
  }
}

export function recolor(colorOf, visibleOf) {
  for (const [key, m] of markers) {
    const visible = visibleOf(key);
    m.setStyle({ fillColor: colorOf(key), fillOpacity: visible ? 0.95 : 0, opacity: visible ? 1 : 0 });
    if (m._path) m._path.style.pointerEvents = visible ? "" : "none";
  }
}

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

export function contains(lat, lng) {
  return map.getBounds().contains([lat, lng]);
}

export function setChangesVisible(visible) {
  if (visible) changeLayer.addTo(map);
  else changeLayer.remove();
}
