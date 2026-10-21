// 지도 화면 진입점: 지역 선택 → 마커 → 클릭 상세 → 슬라이더 재채점·순위표 (plan.md §1.1 흐름 1~3)
//
// [이 파일이 하는 일]
//   web-draft의 지도 화면(index.html)을 움직이는 중심 코드입니다. frontend의 MapScreen.tsx와 같은 역할입니다.
//   1) 로그인 확인 → 데이터(meta·rules·regions) 읽기 → 지도 준비(카카오맵 키가 있으면 카카오, 없으면 Leaflet)
//   2) 지역을 고르면 그 지역 지점을 읽어 마커를 찍는다
//   3) 슬라이더·체크박스를 바꾸면 0.12초 뒤 모든 지점을 다시 채점(rescore)하고 화면을 다시 그린다(render)
//   화면 조각(가중치 패널, 순위표, 지점 상세 등)을 그리는 함수는 panel.js에 있습니다.
//   state: 화면 전체가 함께 쓰는 값 보관 상자(지금 지역, 가중치, 점수 등)
import * as api from "./api.js";
import { computeScore } from "./score.js";
import { KAKAO_JS_KEY } from "./map-config.js";
import { esc, renderPointSheet, renderRankTable, renderScoreNotice, renderSummary, renderWeightPanel, rankOrder } from "./panel.js";
import { requireSession } from "./auth.js";

const $ = (s) => document.querySelector(s);
const session = requireSession();
let mapView;   // 카카오맵(키가 있을 때) 또는 Leaflet — 같은 함수 이름을 쓴다

// 지도 그리기 도구를 고른다. 카카오맵 SDK를 못 불러오면(키 오류·인터넷 없음) Leaflet으로 대신한다
async function loadMapView() {
  if (KAKAO_JS_KEY) {
    try {
      const kakaoView = await import("./map-kakao.js");
      await kakaoView.loadSdk(KAKAO_JS_KEY);
      return kakaoView;
    } catch (e) {
      console.warn(`${e.message} → 기본 지도(Leaflet)로 표시합니다.`);
    }
  }
  return import("./map.js");
}
const TOP_N = 20;          // 순위표 지점 수
const DEBOUNCE_MS = 120;   // 슬라이더를 멈춘 뒤 다시 채점할 때까지 기다리는 시간(0.12초)

const state = {
  meta: null, rules: null, regions: null,
  regionId: null, points: [], details: {}, changes: [],
  weights: [], selected: [], defaultWeights: [],
  scores: new Map(), baseRank: new Map(), status: { error: null, warnings: [] },
  gradeFilter: new Set(), selectedKey: null,
};

const gradeMeta = (label) => state.rules.grades.find((g) => g.label === label);
const colorOf = (key) => {
  const s = state.scores.get(key);
  return s && s.grade ? gradeMeta(s.grade).color : getComputedStyle(document.documentElement).getPropertyValue("--grade-none").trim();
};
const scoreOf = (key) => state.scores.get(key)?.score ?? null;

// 지금 가중치·켜짐 상태로 모든 지점을 다시 채점한다. status에는 '점수를 낼 수 있는 설정인지'가 남는다
function rescore() {
  const { grades, params } = state.rules;
  state.scores.clear();
  let status = { error: null, warnings: [] };
  for (const p of state.points) {
    const res = computeScore(p.r, state.weights, state.selected, grades, params);
    state.scores.set(p.key, res);
    status = res;
  }
  if (!state.points.length) status = computeScore(Array(state.weights.length).fill(0), state.weights, state.selected, grades, params);
  state.status = status;
}

// 기본 가중치 기준 순위(순위표의 '기본' 칸과 ▲▼ 변동 비교용)
function computeBaseRank() {
  const all = state.defaultWeights.map(() => true);
  const base = new Map(state.points.map((p) => [p.key, computeScore(p.r, state.defaultWeights, all, state.rules.grades, state.rules.params).score]));
  state.baseRank = new Map(rankOrder(state.points, (k) => base.get(k)).map((p, i) => [p.key, i + 1]));
}

// 채점 결과로 화면 전체(안내, 마커 색, 요약, 순위표, 추천, 열린 상세)를 다시 그린다
function render() {
  const blocked = !!state.status.error;
  $("#score-blocked").hidden = !blocked;
  $("#score-blocked div").textContent = state.status.error === "ZERO_WEIGHT"
    ? "가중치 합이 0이라 계산을 멈췄습니다" : "위험요인을 2개 이상 선택하세요";
  renderScoreNotice($("#score-notice"), state.status);
  mapView.recolor(colorOf, (k) => {
    const s = state.scores.get(k);
    return !s?.grade || state.gradeFilter.has(s.grade);
  });
  renderSummary($("#summary"), state.points, state.scores, state.rules.grades);
  renderRankTable($(".rank-table"), {
    current: blocked ? [] : rankOrder(state.points, scoreOf), baseRank: state.baseRank, topN: TOP_N,
    colorOf, scoreOf, onClick: openPoint,
  });
  renderRecommend();
  if (state.selectedKey) renderSheet();
}

// 추천 TOP 3: 지금 지도 화면 안(등급 필터 통과)에서 점수가 가장 낮은 3곳
function renderRecommend() {
  const list = $("#recommend-list");
  if (!mapView || !state.points.length) return;
  if (state.status.error) {
    list.innerHTML = `<li class="empty">점수 계산이 멈춰 추천할 수 없습니다.</li>`;
    return;
  }
  const top = state.points
    .filter((p) => {
      const s = state.scores.get(p.key);
      return s?.score != null && state.gradeFilter.has(s.grade) && mapView.contains(p.lat, p.lng);
    })
    .sort((a, b) => scoreOf(a.key) - scoreOf(b.key) || a.name.localeCompare(b.name, "ko"))
    .filter(function (p) { const n = p.name.trim(); return !this.has(n) && this.add(n); }, new Set())   // 같은 이름(한 건물 여러 대)은 하나만
    .slice(0, 3);
  if (!top.length) {
    list.innerHTML = `<li class="empty">지도 화면 안에 표시된 지점이 없습니다. 지도를 움직여 보세요.</li>`;
    return;
  }
  list.innerHTML = top.map((p, i) => {
    const s = state.scores.get(p.key), g = gradeMeta(s.grade);
    return `<li><button type="button" data-key="${p.key}">
      <span class="rank">${i + 1}</span>
      <span class="dot" style="background:${g.color}"></span>
      <span class="name">${esc(p.name)}</span>
      <span class="meta">${g.emoji} ${esc(s.grade)} · <b>${s.score.toFixed(1)}</b>점</span>
    </button></li>`;
  }).join("");
}

// 디바운스: 연달아 불려도 마지막 호출 뒤 0.12초가 지나야 한 번만 다시 채점한다
let timer = null;
function scheduleRescore() {
  clearTimeout(timer);
  timer = setTimeout(() => { rescore(); render(); }, DEBOUNCE_MS);
}

function renderSheet() {
  const detail = state.details[state.selectedKey];
  if (!detail) return;
  const sheet = $(".point-sheet");
  renderPointSheet(sheet, { detail, rules: state.rules, state, current: state.scores.get(state.selectedKey), gradeMeta,
    disclaimer: state.meta.disclaimer });
  sheet.querySelector(".close").addEventListener("click", closePoint);
}

// 지점 상세 열기·닫기
function openPoint(key) {
  state.selectedKey = key;
  renderSheet();
  $(".point-sheet").classList.add("open");
  mapView.select(key);
}

function closePoint() {
  state.selectedKey = null;
  $(".point-sheet").classList.remove("open");
  mapView.clearSelection();
}

// 지역 바꾸기: 그 지역의 지점·상세·추가삭제 파일을 읽고, 채점하고, 마커를 다시 찍고, 주소창 ?region=도 바꾼다
async function loadRegion(rid) {
  closePoint();
  state.regionId = rid;
  const region = state.regions.regions.find((r) => r.region_id === rid);
  // '임시(무효)'는 지역별로 판단(contracts 1.1.0). r1_status가 없는 이전 번들은 meta.r1_confirmed로 대신한다.
  const r1 = region.r1_status ?? (state.meta.r1_confirmed ? "confirmed" : "provisional");
  $("#badge-provisional").hidden = r1 !== "provisional";
  $("#watermark").hidden = r1 !== "provisional";
  $("#badge-nossid").hidden = r1 !== "no_ssid";
  const [pts, details, changes] = await Promise.all([api.getPoints(rid), api.getDetailMap(rid), api.getChanges(rid)]);
  state.points = pts.points;
  state.details = details;
  state.changes = changes.changes;
  computeBaseRank();
  rescore();
  mapView.showPoints(state.points, colorOf, region.bbox);
  mapView.showChanges(state.changes, $("#layer-changes").checked);
  $("#changes-info").textContent = changes.collection_count >= 2
    ? `${changes.collection_count}회 수집, 기간 ${changes.snapshots[0]} ~ ${changes.snapshots.at(-1)} · 추가 ${changes.changes.filter((c) => c.change === "added").length} / 삭제 ${changes.changes.filter((c) => c.change === "removed").length}`
    : `스냅샷 ${changes.collection_count}회 — 비교하려면 2회 이상 필요`;
  $("#search-list").innerHTML = state.points.map((p) => `<option value="${p.name.replace(/"/g, "&quot;")}"></option>`).join("");
  const url = new URL(location.href);
  url.searchParams.set("region", rid);
  history.replaceState(null, "", url);
  render();
}

// 시도·시군구 선택 상자를 채우고, 처음 보여 줄 지역을 정한다(?region → 회원 지역 → 기본 지역 → 첫 지역)
function setupRegionPicker() {
  const avail = state.regions.regions.filter((r) => r.available);
  const sidoSel = $("#sido"), sggSel = $("#sigungu");
  const sidos = [...new Map(avail.map((r) => [r.sido_code, r.sido])).entries()];
  sidoSel.innerHTML = sidos.map(([c, n]) => `<option value="${c}">${n}</option>`).join("");
  const fillSgg = () => {
    sggSel.innerHTML = avail.filter((r) => r.sido_code === sidoSel.value)
      .map((r) => `<option value="${r.region_id}">${r.sigungu} (${r.count.toLocaleString()})</option>`).join("");
  };
  sidoSel.addEventListener("change", () => { fillSgg(); loadRegion(sggSel.value); });
  sggSel.addEventListener("change", () => loadRegion(sggSel.value));
  const want = new URLSearchParams(location.search).get("region");
  // 회원이면 가입 때 적은 지역(데이터가 있을 때만)을 먼저 보여준다
  // (region_id가 없는 예전 세션은 시도·시군구 이름으로 찾는다)
  const home = session?.type !== "member" ? null
    : avail.find((r) => session.region_id && r.region_id === session.region_id)
      ?? (session.sigungu ? avail.find((r) => r.sido === session.sido && r.sigungu === session.sigungu) : null);
  const initial = avail.find((r) => r.region_id === want) ?? home ?? avail.find((r) => r.region_id === state.regions.default_region_id) ?? avail[0];
  sidoSel.value = initial.sido_code;
  fillSgg();
  sggSel.value = initial.region_id;
  return initial.region_id;
}

// 가중치 패널·초기화 버튼·등급 필터·추가삭제 레이어·검색창에 동작을 연결한다
function setupControls() {
  const resetBtn = $("#reset-weights");
  const panel = $("#weight-panel");
  const draw = () => renderWeightPanel(panel, state.rules, state, scheduleRescore);
  draw();
  resetBtn.addEventListener("click", () => {
    state.weights = [...state.defaultWeights];
    state.selected = state.defaultWeights.map(() => true);
    draw();
    rescore(); render();
  });
  $("#grade-filter").innerHTML = state.rules.grades.map((g) =>
    `<label><input type="checkbox" value="${g.label}" checked> ${g.emoji} ${g.label}</label>`).join("");
  $("#grade-filter").addEventListener("change", (e) => {
    if (e.target.checked) state.gradeFilter.add(e.target.value); else state.gradeFilter.delete(e.target.value);
    render();
  });
  $("#layer-changes").addEventListener("change", (e) => mapView.setChangesVisible(e.target.checked));
  $("#search").addEventListener("change", (e) => {
    const p = state.points.find((x) => x.name === e.target.value);
    if (p) openPoint(p.key);
  });
}

// 등급 색을 rules.json 값으로 CSS 변수(--grade-*)에 덮어쓴다(색의 기준은 rules.json)
function applyGradeColors() {
  const root = document.documentElement.style;
  const vars = ["--grade-low", "--grade-mid", "--grade-high"];
  state.rules.grades.forEach((g, i) => vars[i] && root.setProperty(vars[i], g.color));
}

// 시작점: 데이터 읽기 → 기본값 채우기 → 지도 준비 → 조작 연결 → 첫 지역 표시
async function main() {
  try {
    state.meta = await api.init();
  } catch (e) {
    $("#fatal").hidden = false;
    $("#fatal").textContent = `데이터 번들을 불러오지 못했습니다(${e.message}). scripts/sync_bundle 실행 여부와 http.server 실행 위치(web-draft/)를 확인하세요.`;
    return;
  }
  [state.rules, state.regions] = await Promise.all([api.getRules(), api.getRegions()]);
  state.defaultWeights = state.rules.rules.map((r) => r.max_points);
  state.weights = [...state.defaultWeights];
  state.selected = state.rules.rules.map(() => true);
  state.gradeFilter = new Set(state.rules.grades.map((g) => g.label));
  applyGradeColors();
  $("#badge-mock").hidden = !state.meta.is_mock;
  $("#data-date").textContent = `데이터 기준일 ${state.meta.data_reference_date ?? "–"} · 수집 ${state.meta.snapshot_collected_at ?? "–"}`;
  mapView = await loadMapView();
  mapView.initMap($("#map"), { onPointClick: openPoint });
  mapView.onViewChange(renderRecommend);
  $("#recommend-list").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-key]");
    if (btn) openPoint(btn.dataset.key);
  });
  setupControls();
  await loadRegion(setupRegionPicker());
}

if (session) main();
