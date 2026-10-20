// 데이터 접근 (plan.md §6.1 경로 표, docs/requests.md #16).
// 우리 API(NEXT_PUBLIC_API_BASE)를 먼저 쓰고, 응답이 없으면 정적 번들(/data)로 자동 전환한다(시연 백업).
import { config } from "./config";
import type {
  BackgroundDoc, CasesDoc, ChangesDoc, Detail, DetailDoc, KeyIndexDoc, MetaDoc, PointsDoc, RegionsDoc, RulesDoc,
  SensitivityDoc,
} from "./types";

export type DataSource = "api" | "static";

// API가 한 번 응답하지 않으면 5분 동안은 페이지를 옮겨도 바로 정적 번들을 쓴다(매번 연결 실패를 기다리지 않게)
const DOWN_KEY = "wt_api_down_until";
const DOWN_MS = 5 * 60 * 1000;
function apiRecentlyDown(): boolean {
  try {
    return typeof window !== "undefined" && Number(sessionStorage.getItem(DOWN_KEY) ?? 0) > Date.now();
  } catch {
    return false;
  }
}
function markApiDown() {
  try {
    sessionStorage.setItem(DOWN_KEY, String(Date.now() + DOWN_MS));
  } catch {
    /* 저장소를 못 쓰면 이번 페이지에서만 */
  }
}

let source: DataSource = config.apiBase && !apiRecentlyDown() ? "api" : "static";
const listeners = new Set<(s: DataSource) => void>();
export const dataSource = () => source;
export function onDataSourceChange(fn: (s: DataSource) => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

const API_TIMEOUT_MS = 8000;

async function fetchJson<T>(url: string, timeoutMs?: number): Promise<T> {
  const ctl = new AbortController();
  const timer = timeoutMs ? setTimeout(() => ctl.abort(), timeoutMs) : undefined;
  try {
    const res = await fetch(url, { signal: ctl.signal });
    if (!res.ok) throw Object.assign(new Error(`${res.status} ${url}`), { status: res.status });
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

/** apiPath: API 경로(/meta 등), staticPath: 정적 번들 상대경로(meta.json 등) */
async function get<T>(apiPath: string, staticPath: string): Promise<T> {
  if (source === "api") {
    try {
      return await fetchJson<T>(`${config.apiBase}${apiPath}`, API_TIMEOUT_MS);
    } catch (e) {
      // 404는 "없는 데이터"이므로 전환하지 않는다. 네트워크·서버 오류만 정적 번들로 전환
      if ((e as { status?: number }).status === 404) throw e;
      console.warn("API 응답 없음 → 정적 번들로 전환합니다:", (e as Error).message);
      source = "static";
      markApiDown();
      listeners.forEach((fn) => fn(source));
    }
  }
  return fetchJson<T>(`${config.dataBase}/${staticPath}`);
}

export const getMeta = () => get<MetaDoc>("/meta", "meta.json");
export const getRules = () => get<RulesDoc>("/rules", "rules.json");
export const getRegions = () => get<RegionsDoc>("/regions", "regions.json");
export const getPoints = (rid: string) => get<PointsDoc>(`/regions/${rid}/points`, `points/${rid}.json`);
export const getChanges = (rid: string) => get<ChangesDoc>(`/regions/${rid}/changes`, `changes/${rid}.json`);
export const getSensitivity = (rid: string) =>
  get<SensitivityDoc>(`/regions/${rid}/sensitivity`, `sensitivity/${rid}.json`);
export const getBackground = () => get<BackgroundDoc>("/background", "background.json");
export const getCases = () => get<CasesDoc>("/cases", "cases.json");

/** 지점 상세: API는 /points/{key}, 정적 번들은 key_index → detail/{region}.json */
export async function getDetail(key: string): Promise<Detail | null> {
  if (source === "api") {
    try {
      return await get<Detail>(`/points/${key}`, "__unused__");
    } catch (e) {
      if ((e as { status?: number }).status === 404) return null;
    }
  }
  const idx = await fetchJson<KeyIndexDoc>(`${config.dataBase}/key_index.json`);
  const rid = idx[key];
  if (!rid) return null;
  return (await fetchJson<DetailDoc>(`${config.dataBase}/detail/${rid}.json`))[key] ?? null;
}

/** GPS 좌표 → 가장 가까운 지역 (#18). API가 없으면 regions.json 중심점 중 가장 가까운 곳 */
export async function nearestRegion(lat: number, lng: number, regions: RegionsDoc): Promise<string | null> {
  if (source === "api") {
    try {
      const r = await fetchJson<{ region_id: string }>(
        `${config.apiBase}/nearest?lat=${lat}&lng=${lng}`, API_TIMEOUT_MS);
      return r.region_id;
    } catch {
      /* 아래 근사로 */
    }
  }
  const avail = regions.regions.filter((r) => r.available);
  let best: string | null = null;
  let bestD = Infinity;
  for (const r of avail) {
    const dy = r.center.lat - lat;
    const dx = (r.center.lng - lng) * Math.cos((lat * Math.PI) / 180);
    const d = dx * dx + dy * dy;
    if (d < bestD) [best, bestD] = [r.region_id, d];
  }
  return best;
}

export interface SearchHit {
  key: string; region_id: string; sido: string; sigungu: string; name: string;
  address: string | null; place_detail: string | null; lat: number; lng: number;
}

/** 장소 검색. API(전국, 장소명·주소)를 먼저 쓰고, 없으면 지금 지역의 장소명에서 찾는다 */
export async function searchPoints(
  q: string, regionId: string | null, localPoints: PointsDoc["points"], region?: { sido: string; sigungu: string },
): Promise<{ hits: SearchHit[]; scope: "전국" | "지금 지역" }> {
  if (source === "api") {
    try {
      const params = new URLSearchParams({ q, limit: "15", ...(regionId ? { region_id: regionId } : {}) });
      const r = await fetchJson<{ hits: SearchHit[] }>(`${config.apiBase}/search?${params}`, API_TIMEOUT_MS);
      return { hits: r.hits, scope: "전국" };
    } catch {
      /* 아래 지역 내 장소명 검색으로 */
    }
  }
  const toks = q.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = localPoints
    .filter((p) => toks.every((t) => p.name.toLowerCase().includes(t)))
    .slice(0, 15)
    .map((p) => ({ key: p.key, region_id: regionId ?? "", sido: region?.sido ?? "", sigungu: region?.sigungu ?? "",
      name: p.name, address: null, place_detail: null, lat: p.lat, lng: p.lng }));
  return { hits, scope: "지금 지역" };
}
