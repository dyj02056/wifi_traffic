// 사이드바(weight-panel), 순위표(rank-table), 지점 상세(point-sheet) 렌더링.

export function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const fmt = (n) => (n == null ? "–" : Number(n).toFixed(2).replace(/\.?0+$/, ""));

// ── weight-panel ──────────────────────────────────────────
export function renderWeightPanel(el, rules, state, onChange) {
  el.innerHTML = rules.rules.map((r, i) => `
    <div class="rule ${state.selected[i] ? "" : "off"}" data-i="${i}">
      <input type="checkbox" id="sel-${r.id}" ${state.selected[i] ? "checked" : ""} aria-label="${esc(r.id)} 선택">
      <label for="sel-${r.id}" class="name">${esc(r.id)} ${esc(r.name)}
        ${r.is_assumption ? '<span class="badge assumption" title="가정 기반 규칙">가정</span>' : ""}</label>
      <span></span>
      <input type="range" min="0" max="${2 * r.max_points}" step="1" value="${state.weights[i]}"
             aria-label="${esc(r.id)} 가중치" ${state.selected[i] ? "" : "disabled"}>
      <output>${state.weights[i]}</output>
      <div class="one-liner">${esc(r.one_liner)} (기본 ${r.max_points}점)</div>
    </div>`).join("");
  el.querySelectorAll(".rule").forEach((row) => {
    const i = Number(row.dataset.i);
    const cb = row.querySelector("input[type=checkbox]");
    const sl = row.querySelector("input[type=range]");
    const out = row.querySelector("output");
    cb.addEventListener("change", () => {
      state.selected[i] = cb.checked;
      row.classList.toggle("off", !cb.checked);
      sl.disabled = !cb.checked;
      onChange();
    });
    sl.addEventListener("input", () => {
      state.weights[i] = Number(sl.value);
      out.textContent = sl.value;
      onChange();
    });
  });
}

export function renderScoreNotice(el, status) {
  if (status.error === "TOO_FEW_RULES") {
    el.innerHTML = '<div class="notice error">위험요인을 2개 이상 선택해야 점수를 계산합니다.</div>';
  } else if (status.error === "ZERO_WEIGHT") {
    el.innerHTML = '<div class="notice error">선택한 위험요인의 가중치 합이 0입니다. 가중치를 올려 주세요.</div>';
  } else if (status.warnings.includes("LOW_MAXSUM")) {
    el.innerHTML = '<div class="notice warn">선택한 요인의 만점 합이 작아 점수가 소수 요인에 크게 좌우됩니다.</div>';
  } else {
    el.innerHTML = "";
  }
}

// ── 상단 요약 ─────────────────────────────────────────────
export function renderSummary(el, points, scores, grades) {
  const counts = Object.fromEntries(grades.map((g) => [g.label, 0]));
  let sum = 0, n = 0;
  for (const p of points) {
    const s = scores.get(p.key);
    if (s && s.score != null) { counts[s.grade] += 1; sum += s.score; n += 1; }
  }
  el.innerHTML = `<span>지점 <span class="num">${points.length.toLocaleString()}</span></span>`
    + grades.map((g) => `<span>${g.emoji} ${esc(g.label)} <span class="num">${counts[g.label].toLocaleString()}</span></span>`).join("")
    + `<span>평균 <span class="num">${n ? fmt(Math.floor((sum / n) * 100 + 0.5) / 100) : "–"}</span>점</span>`;
}

// ── rank-table: 기본 상위 20 vs 현재 상위 20 ──────────────
export function rankOrder(points, scoreOf) {
  return points
    .filter((p) => scoreOf(p.key) != null)
    .sort((a, b) => scoreOf(b.key) - scoreOf(a.key) || (a.key < b.key ? -1 : 1));
}

export function renderRankTable(el, { current, baseRank, topN, colorOf, scoreOf, onClick }) {
  const tbody = el.querySelector("tbody");
  const prevTops = new Map([...tbody.querySelectorAll("tr")].map((tr) => [tr.dataset.key, tr.getBoundingClientRect().top]));
  const top = current.slice(0, topN);
  const baseTop = new Set([...baseRank.entries()].filter(([, r]) => r <= topN).map(([k]) => k));
  const overlap = top.filter((p) => baseTop.has(p.key)).length;
  el.querySelector(".overlap").textContent = top.length ? `기본 기준 상위 ${topN}과 겹침 ${overlap}개` : "";
  tbody.innerHTML = top.map((p, i) => {
    const b = baseRank.get(p.key);
    const d = b - (i + 1);
    const delta = d > 0 ? `<span class="up">▲${d}</span>` : d < 0 ? `<span class="down">▼${-d}</span>` : "–";
    return `<tr data-key="${esc(p.key)}" class="${d > 0 ? "flash-up" : d < 0 ? "flash-down" : ""}">
      <td class="num">${i + 1}</td>
      <td><span class="dot" style="background:${colorOf(p.key)}"></span>${esc(p.name)}</td>
      <td class="num">${fmt(scoreOf(p.key))}</td>
      <td class="num">${b}</td><td class="num">${delta}</td></tr>`;
  }).join("");
  // FLIP: 이전 위치에서 새 위치로 미끄러지듯 이동
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
    tbody.querySelectorAll("tr").forEach((tr) => {
      const old = prevTops.get(tr.dataset.key);
      if (old == null) return;
      const dy = old - tr.getBoundingClientRect().top;
      if (!dy) return;
      tr.style.transition = "none";
      tr.style.transform = `translateY(${dy}px)`;
      requestAnimationFrame(() => { tr.style.transition = ""; tr.style.transform = ""; });
    });
  }
  tbody.querySelectorAll("tr").forEach((tr) => tr.addEventListener("click", () => onClick(tr.dataset.key)));
}

// ── point-sheet ───────────────────────────────────────────
const EVIDENCE_LABELS = {
  ssid: "SSID", facility_type: "설치시설구분", place_detail: "설치장소상세", install_ym: "설치연월",
  provider: "서비스제공사", manager: "관리기관", manager_tel: "관리기관 전화", data_date: "데이터기준일자",
  address: "주소", open_ap_within_radius: "반경 내 개방형 AP",
};
const FLAG_LABELS = {
  R1_ssid_missing: "SSID 정보 없음(가정 비율)", R1_unlabeled: "SSID 라벨 없음(가정 비율)", R1_unknown: "SSID 분류 불명(가정 비율)", R2_unmapped: "시설구분 미등록(가정 비율)",
  R4_missing: "설치연월 결측(가정 비율)", R4_year_only: "설치연도만 있음", R5_boundary: "시군구 경계 근처 — 밀집도 과소평가 가능",
  R7_invalid_tel: "전화번호 형식 불일치", R8_missing: "데이터기준일자 결측",
  COORD_suspect: "좌표 이상 의심 — 지역 지도 범위 계산에서 제외(점수에는 영향 없음)",
};

export function renderPointSheet(el, { detail, rules, state, current, gradeMeta, disclaimer }) {
  const wsum = rules.rules.reduce((a, r, i) => a + (state.selected[i] ? state.weights[i] : 0), 0);
  const g = gradeMeta(current?.grade);
  const scoreTxt = current?.score != null ? fmt(current.score) : "계산 중지";
  const rows = detail.breakdown.map((b, i) => {
    const on = state.selected[i] && wsum > 0;
    const contrib = on ? (100 * state.weights[i] * b.ratio) / wsum : 0;
    return `<div class="row ${on ? "" : "off"}">
      <div class="head"><span>${esc(b.id)} ${esc(b.name)} ${b.is_assumption ? '<span class="badge assumption">가정</span>' : ""}</span>
        <span>${on ? `${fmt(Math.floor(contrib * 100 + 0.5) / 100)}점` : "미선택"} · 비율 ${fmt(b.ratio)}</span></div>
      <div class="bar"><span style="width:${(b.ratio * 100).toFixed(1)}%"></span></div>
      <div class="reason">${esc(b.reason)}</div></div>`;
  }).join("");
  const ev = Object.entries(detail.evidence).map(([k, v]) =>
    `<dt>${esc(EVIDENCE_LABELS[k] ?? k)}</dt><dd>${v == null || v === "" ? "<em>없음</em>" : esc(v)}</dd>`).join("");
  const flags = detail.flags.length
    ? `<ul>${detail.flags.map((f) => `<li>${esc(FLAG_LABELS[f] ?? f)}</li>`).join("")}</ul>` : "<p>없음</p>";
  el.innerHTML = `
    <button class="close" aria-label="닫기">✕</button>
    <h2>${esc(detail.name)}</h2>
    <div class="sheet-disclaimer">※ ${esc(disclaimer)}</div>
    <div><span class="score-big" style="color:${g?.color ?? "inherit"}">${scoreTxt}</span>
      ${g ? `<span>${g.emoji} ${esc(g.label)}</span>` : ""}
      <div class="reason">현재 가중치 기준 · 기본 가중치 기준 ${fmt(detail.score)}점(${esc(detail.grade)})</div></div>
    <section class="panel breakdown"><h3>위험요인별 점수 (R1~R8)</h3>${rows}</section>
    <section class="panel"><h3>설명</h3><div class="explanation">${esc(detail.explanation.text)}
      <div class="src">${detail.explanation.source === "ai" ? "AI 생성(근거값만 인용·검증 통과)" : "근거값 기반 자동 설명"}</div></div></section>
    <section class="panel"><h3>안전하게 쓰는 법</h3>
      <ul class="tips">${detail.safety_tips.map((t, i) => `<li><label><input type="checkbox" id="tip-${i}"> ${esc(t)}</label></li>`).join("")}</ul></section>
    <section class="panel"><h3>신고·문의</h3>
      <p>${esc(detail.report_contact.manager ?? "관리기관 정보 없음")} ${detail.report_contact.tel ? `· <a href="tel:${esc(detail.report_contact.tel)}">${esc(detail.report_contact.tel)}</a>` : "· 전화번호 없음"}</p></section>
    <section class="panel"><h3>근거값 (원본 데이터)</h3><dl class="evidence">${ev}</dl></section>
    <section class="panel"><h3>데이터 참고</h3>${flags}</section>`;
}
