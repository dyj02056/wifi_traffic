"use client";
// ★ 메인 지도 화면 (plan.md §9.3 /map + docs/requests.md #16 #18 #20 #23 #24)
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { nearestRegion } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { useChanges, useDataSource, useDetail, useMeta, usePoints, useRegions, useRules } from "@/lib/queries";
import { computeScore, type ScoreResult } from "@/lib/score";
import type { RegionsDoc } from "@/lib/types";
import { useAppStore } from "@/store/useAppStore";
import { KakaoMap } from "./KakaoMap";
import { PointSheet } from "./PointSheet";
import { RankTable, type RankRow } from "./RankTable";
import { SearchBox } from "./SearchBox";
import { Summary } from "./Summary";
import { TopNav } from "./TopNav";
import { ScoreNotice, WeightPanel } from "./WeightPanel";

const TOP_N = 20;
const DEBOUNCE_MS = 120;
// 데이터가 아직 없을 때 넘기는 빈 배열은 하나로 고정한다. 렌더마다 새 []를 넘기면 지도가 매번 범위를 다시 맞추고
// idle → onViewChange → 다시 렌더가 반복된다(Maximum update depth exceeded)
const NO_POINTS: never[] = [];
const NO_CHANGES: never[] = [];

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** 첫 지역: ?region → 회원 가입 지역 → default_region_id(서초구 임시, #20) → 데이터 있는 첫 지역 (#18) */
function pickInitial(regions: RegionsDoc, want: string | null, home: string | null | undefined) {
  const avail = regions.regions.filter((r) => r.available);
  const has = (id?: string | null) => (id ? avail.find((r) => r.region_id === id)?.region_id : undefined);
  return has(want) ?? has(home) ?? has(regions.default_region_id) ?? avail[0]?.region_id ?? null;
}

export function MapScreen() {
  const router = useRouter();
  const search = useSearchParams();
  const session = useSession();
  const source = useDataSource();
  const meta = useMeta();
  const rules = useRules();
  const regions = useRegions();
  const st = useAppStore();
  const [picked, setPicked] = useState<string | null>(null);
  const [inView, setInView] = useState<((lat: number, lng: number) => boolean) | null>(null);
  const [gps, setGps] = useState<{ busy: boolean; msg: string }>({ busy: false, msg: "" });
  const [dimMap, setDimMap] = useState(true);   // 배경 지도 색을 30%만 남겨 마커가 먼저 보이게 (A′)
  const [focus, setFocus] = useState<{ lat: number; lng: number; level: number; seq: number } | null>(null);
  const focusOn = (lat: number, lng: number, level: number) => setFocus((f) => ({ lat, lng, level, seq: (f?.seq ?? 0) + 1 }));

  // 로그인 안 했으면 인트로로
  useEffect(() => {
    if (session === null) router.replace("/");
  }, [session, router]);

  useEffect(() => {
    if (rules.data) st.initRules(rules.data.rules.map((r) => r.max_points), rules.data.grades.map((g) => g.label));
  }, [rules.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const initial = useMemo(() => (regions.data && session !== undefined
    ? pickInitial(regions.data, search.get("region"), session?.type === "member" ? session.user.region_id : null)
    : null), [regions.data, session, search]);
  const regionId = picked ?? initial;

  const chooseRegion = useCallback((rid: string) => {
    setPicked(rid);
    setFocus(null);       // 검색으로 고른 위치는 지역을 직접 바꾸면 잊는다(검색 쪽은 이 다음에 다시 지정)
    st.selectPoint(null);
    const q = new URLSearchParams(search.toString());
    q.set("region", rid);
    router.replace(`/map?${q}`, { scroll: false });
  }, [router, search, st]);

  const region = regions.data?.regions.find((r) => r.region_id === regionId) ?? null;
  const points = usePoints(regionId);
  const changes = useChanges(regionId);
  const detail = useDetail(st.selectedKey);

  // ── 채점 (슬라이더 디바운스 후) ──
  const weights = useDebounced(st.weights, DEBOUNCE_MS);
  const selected = useDebounced(st.selected, DEBOUNCE_MS);
  const grades = rules.data?.grades;
  const params = rules.data?.params as { MIN_SELECTED_RULES: number; LOW_MAXSUM_WARN: number } | undefined;
  const pts = points.data?.points;

  const scores = useMemo(() => {
    const m = new Map<string, ScoreResult>();
    if (!pts || !grades || !params || !weights.length) return m;
    for (const p of pts) m.set(p.key, computeScore(p.r, weights, selected, grades, params));
    return m;
  }, [pts, grades, params, weights, selected]);
  const status = useMemo<ScoreResult>(() => (grades && params && weights.length
    ? computeScore(Array(weights.length).fill(0), weights, selected, grades, params)
    : { score: null, grade: null, error: null, warnings: [] }), [grades, params, weights, selected]);

  const baseRank = useMemo(() => {
    const m = new Map<string, number>();
    [...(pts ?? [])].sort((a, b) => b.score - a.score || (a.key < b.key ? -1 : 1)).forEach((p, i) => m.set(p.key, i + 1));
    return m;
  }, [pts]);

  const gradeColor = useMemo(() => new Map<string, string>((grades ?? []).map((g) => [g.label, g.color])), [grades]);
  const colorOf = useCallback((key: string) => {
    const s = scores.get(key);
    return (s?.grade && gradeColor.get(s.grade)) || "var(--grade-none)";
  }, [scores, gradeColor]);
  // grades 순서(낮음·주의·높음) → 마커 기호·크기 단계
  const gradeLevel = useMemo(() => new Map<string, "low" | "mid" | "high">(
    (grades ?? []).map((g, i, all) => [g.label, i === 0 ? "low" : i === all.length - 1 ? "high" : "mid"])), [grades]);
  const levelOf = useCallback((key: string) => {
    const s = scores.get(key);
    return (s?.grade && gradeLevel.get(s.grade)) || "";
  }, [scores, gradeLevel]);
  const visibleOf = useCallback((key: string) => {
    const s = scores.get(key);
    return !s?.grade || st.gradeFilter.has(s.grade);
  }, [scores, st.gradeFilter]);

  const ranked = useMemo(() => (pts ?? [])
    .filter((p) => scores.get(p.key)?.score != null)
    .sort((a, b) => scores.get(b.key)!.score! - scores.get(a.key)!.score! || (a.key < b.key ? -1 : 1)), [pts, scores]);
  const rankRows: RankRow[] = ranked.slice(0, TOP_N).map((p) => ({
    key: p.key, name: p.name, score: scores.get(p.key)!.score!, baseRank: baseRank.get(p.key)!, color: colorOf(p.key),
  }));
  const baseTop = new Set([...baseRank].filter(([, r]) => r <= TOP_N).map(([k]) => k));
  const overlap = rankRows.filter((r) => baseTop.has(r.key)).length;

  const counts: Record<string, number> = {};
  let sum = 0, n = 0;
  for (const s of scores.values()) if (s.score != null && s.grade) { counts[s.grade] = (counts[s.grade] ?? 0) + 1; sum += s.score; n += 1; }

  // 추천 TOP 3: 지금 지도 화면 안에서 점수가 가장 낮은 곳 (지도가 없으면 지역 전체)
  // 같은 이름(한 건물의 공유기 여러 대)은 하나만 — 강남구민체육관 3대가 TOP 3를 다 차지하던 문제
  const seenNames = new Set<string>();
  const recommend = (pts ?? [])
    .filter((p) => { const s = scores.get(p.key); return s?.score != null && st.gradeFilter.has(s.grade!) && (!inView || inView(p.lat, p.lng)); })
    .sort((a, b) => scores.get(a.key)!.score! - scores.get(b.key)!.score! || (a.key < b.key ? -1 : 1))
    .filter((p) => { const n = p.name.trim(); if (seenNames.has(n)) return false; seenNames.add(n); return true; })
    .slice(0, 3);

  const onGps = () => {
    if (!navigator.geolocation || !regions.data) return setGps({ busy: false, msg: "이 브라우저는 위치 기능을 지원하지 않습니다." });
    setGps({ busy: true, msg: "위치를 확인하는 중…" });
    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      const rid = await nearestRegion(coords.latitude, coords.longitude, regions.data!);
      const r = regions.data!.regions.find((x) => x.region_id === rid);
      if (r?.available) {
        chooseRegion(r.region_id);
        setGps({ busy: false, msg: `내 위치 근처: ${r.sido} ${r.sigungu}` });
      } else {
        setGps({ busy: false, msg: r ? `${r.sido} ${r.sigungu}은 아직 데이터가 없습니다.` : "근처 지역을 찾지 못했습니다." });
      }
    }, (err) => setGps({ busy: false, msg: err.code === err.PERMISSION_DENIED ? "위치 권한이 거부되었습니다." : "위치를 가져오지 못했습니다." }),
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  };

  if (meta.error || rules.error || regions.error) {
    return <div className="page"><TopNav /><div className="notice error">데이터를 불러오지 못했습니다. API 주소(NEXT_PUBLIC_API_BASE) 또는 정적 번들(public/data, scripts/sync_bundle.sh)을 확인하세요.</div></div>;
  }
  if (!meta.data || !rules.data || !regions.data || session === undefined) return <div className="page"><TopNav /><p className="loading">불러오는 중…</p></div>;

  const r1 = region?.r1_status;
  const badges = (
    <>
      {meta.data.is_mock && <span className="badge mock">샘플 데이터</span>}
      {source === "static" && <span className="badge static" title="API 응답이 없어 정적 백업 데이터를 보여 줍니다">정적 백업 데이터</span>}
      {r1 === "provisional" && <span className="badge provisional">임시(무효) — SSID 라벨 미확정</span>}
      {r1 === "no_ssid" && <span className="badge assumption">SSID 정보 없음 — 보안접속 항목(R1)은 가정값</span>}
    </>
  );
  const avail = regions.data.regions.filter((r) => r.available);
  const sidos = [...new Map(avail.map((r) => [r.sido_code, r.sido])).entries()];

  return (
    <div className="page">
      <TopNav badges={badges} />
      <section className="topbar">
        <div className="region-picker">
          <h2><span className="step">1</span> 지역 선택</h2>
          <div className="fields">
            <label>시도
              <select value={region?.sido_code ?? ""} onChange={(e) => {
                const first = avail.find((r) => r.sido_code === e.target.value);
                if (first) chooseRegion(first.region_id);
              }}>
                {sidos.map(([c, nm]) => <option key={c} value={c}>{nm}</option>)}
              </select>
            </label>
            <label>시군구
              <select value={regionId ?? ""} onChange={(e) => chooseRegion(e.target.value)}>
                {avail.filter((r) => r.sido_code === region?.sido_code).map((r) =>
                  <option key={r.region_id} value={r.region_id}>{r.sigungu} ({r.count.toLocaleString()})</option>)}
              </select>
            </label>
            <label className="grow">장소 검색
              <SearchBox regionId={regionId} region={region ?? undefined} points={pts ?? NO_POINTS}
                onPickPoint={(h) => {
                  if (h.region_id && h.region_id !== regionId) chooseRegion(h.region_id);
                  st.selectPoint(h.key);
                  focusOn(h.lat, h.lng, 3);
                }}
                onPickPlace={async (pl) => {
                  const rid = await nearestRegion(pl.lat, pl.lng, regions.data!);
                  const r = regions.data!.regions.find((x) => x.region_id === rid);
                  if (r?.available && r.region_id !== regionId) chooseRegion(r.region_id);
                  focusOn(pl.lat, pl.lng, 4);
                  setGps({ busy: false, msg: r?.available ? `📍 ${pl.label} 근처 (${r.sido} ${r.sigungu})` : `📍 ${pl.label} — 이 지역은 아직 데이터가 없습니다` });
                }} />
            </label>
          </div>
          <p className="field" id="data-date">데이터 기준일 {meta.data.data_reference_date ?? "–"} · 수집 {meta.data.snapshot_collected_at ?? "–"}
            {meta.data.snapshot_count ? ` · ${meta.data.snapshot_count}회 수집` : ""}</p>
        </div>
        <div className="recommend">
          <h2><span className="step">2</span> 추천 와이파이 TOP 3 <small>지금 지도 화면 안에서 위험요인 점수가 가장 낮은 곳</small></h2>
          <ol className="recommend-list">
            {recommend.length ? recommend.map((p, i) => {
              const s = scores.get(p.key)!;
              const g = rules.data!.grades.find((x) => x.label === s.grade);
              return (
                <li key={p.key}>
                  <button type="button" onClick={() => st.selectPoint(p.key)}>
                    <span className="rank">{i + 1}</span><span className="dot" style={{ background: colorOf(p.key) }} />
                    <span className="name">{p.name}</span>
                    <span className="meta">{g?.emoji} {s.grade} · <b>{s.score!.toFixed(1)}</b>점{i === 0 && <span className="badge pick">추천</span>}</span>
                  </button>
                </li>
              );
            }) : <li className="empty">지금 화면 안에 표시할 지점이 없습니다.</li>}
          </ol>
        </div>
      </section>

      <main className="app">
        <aside className="sidebar">
          <ScoreNotice error={status.error} warnings={status.warnings} />
          <WeightPanel rules={rules.data} />
          <section className="panel layer-toggle">
            <h2>배경 레이어</h2>
            <label><input type="checkbox" checked={st.showChanges} onChange={(e) => st.setShowChanges(e.target.checked)} /> 최근 추가·삭제 지점</label>
            <p className="field">{changes.data && (changes.data.collection_count >= 2
              ? `${changes.data.collection_count}회 수집, 기간 ${changes.data.snapshots[0]} ~ ${changes.data.snapshots.at(-1)} · 추가 ${changes.data.changes.filter((c) => c.change === "added").length} / 삭제 ${changes.data.changes.filter((c) => c.change === "removed").length}`
              : `스냅샷 ${changes.data.collection_count}회 — 비교하려면 2회 이상 필요`)}</p>
          </section>
          <section className="panel grade-filter">
            <h2>등급 필터</h2>
            {rules.data.grades.map((g) => (
              <label key={g.label}><input type="checkbox" checked={st.gradeFilter.has(g.label)} onChange={() => st.toggleGrade(g.label)} /> {g.emoji} {g.label}</label>
            ))}
          </section>
        </aside>

        <div className={`map-wrap${dimMap ? " dim" : ""}`}>
          <KakaoMap points={pts ?? NO_POINTS} bbox={region?.bbox ?? null} colorOf={colorOf} levelOf={levelOf} visibleOf={visibleOf}
            colorVersion={scores} selectedKey={st.selectedKey} changes={changes.data?.changes ?? NO_CHANGES}
            showChanges={st.showChanges} onSelect={st.selectPoint} onViewChange={(fn) => setInView(() => fn)} focus={focus} />
          <Summary total={pts?.length ?? 0} counts={counts} grades={rules.data.grades} avg={n ? Math.floor((sum / n) * 100 + 0.5) / 100 : null} />
          {r1 === "provisional" && <div className="watermark"><span>임시(무효)</span></div>}
          {status.error && <div className="map-overlay"><div>{status.error === "TOO_FEW_RULES" ? "위험요인을 2개 이상 선택하세요" : "가중치 합이 0입니다"}</div></div>}
          {gps.msg && <div className="gps-msg" role="status">{gps.msg}</div>}
          <button type="button" className="dim-btn" onClick={() => setDimMap((v) => !v)} aria-pressed={dimMap}
            title="배경 지도의 색을 흐리게 해 마커가 먼저 보이게 합니다">{dimMap ? "지도 색 원래대로" : "지도 색 흐리게"}</button>
          <button type="button" className="gps-btn" onClick={onGps} disabled={gps.busy} title="누를 때만 위치 권한을 요청합니다">📍 내 위치</button>
        </div>

        <aside className="right-col">
          <RankTable rows={rankRows} overlap={overlap} topN={TOP_N} onClick={st.selectPoint} />
          <PointSheet open={!!st.selectedKey} detail={detail.data} loading={detail.isLoading} rules={rules.data}
            weights={st.weights} selected={st.selected} current={st.selectedKey ? scores.get(st.selectedKey) : undefined}
            onClose={() => st.selectPoint(null)} />
        </aside>
      </main>
    </div>
  );
}
