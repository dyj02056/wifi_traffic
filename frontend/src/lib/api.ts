// 데이터 접근 (plan.md §6.1 경로 표, docs/requests.md #16).
// 우리 API(NEXT_PUBLIC_API_BASE)를 먼저 쓰고, 응답이 없으면 정적 번들(/data)로 자동 전환한다(시연 백업).
import { config } from "./config";
import type {
  BackgroundDoc, CasesDoc, ChangesDoc, Detail, DetailDoc, KeyIndexDoc, MetaDoc, PointsDoc, RegionsDoc, RulesDoc,
  SensitivityDoc,
} from "./types";

export type DataSource = "api" | "static";

// API가 응답하지 않으면 5분 동안은 페이지를 옮겨도 바로 정적 번들을 쓴다(매번 연결 실패를 기다리지 않게).
// 5분이 지나면 다시 API로 돌아간다(새로고침하지 않아도).
const DOWN_KEY = "wt_api_down_until";
const DOWN_MS = 5 * 60 * 1000;
function downUntil(): number {
  try {
    return typeof window !== "undefined" ? Number(sessionStorage.getItem(DOWN_KEY) ?? 0) : 0;
  } catch {
    return 0;
  }
}
function setDownUntil(t: number) {
  try {
    if (t) sessionStorage.setItem(DOWN_KEY, String(t));
    else sessionStorage.removeItem(DOWN_KEY);
  } catch {
    /* 저장소를 못 쓰면 이번 페이지에서만 */
  }
}

let source: DataSource = config.apiBase && downUntil() <= Date.now() ? "api" : "static";
const listeners = new Set<(s: DataSource) => void>();
export const dataSource = () => source;
export function onDataSourceChange(fn: (s: DataSource) => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
function setSource(s: DataSource) {
  if (source === s) return;
  source = s;
  listeners.forEach((fn) => fn(source));
}

let recoverTimer: ReturnType<typeof setTimeout> | undefined;
function scheduleRecover(at: number) {
  clearTimeout(recoverTimer);
  recoverTimer = setTimeout(retryApi, Math.max(0, at - Date.now()));
}
function markApiDown() {
  const until = Date.now() + DOWN_MS;
  setDownUntil(until);
  scheduleRecover(until);
  setSource("static");
}
if (config.apiBase && source === "static" && typeof window !== "undefined") scheduleRecover(downUntil());

/** 백업 모드를 끝내고 다시 API를 쓴다(5분 뒤 자동, 또는 "다시 시도" 버튼). 구독자가 받은 문서를 다시 받는다 */
export function retryApi() {
  if (!config.apiBase) return;
  clearTimeout(recoverTimer);
  setDownUntil(0);
  if (source === "api") listeners.forEach((fn) => fn(source));
  else setSource("api");
}

// 한동안 안 쓰면 Vercel 함수·Neon이 잠들어 첫 응답이 10초 넘게 걸린다(DB connect_timeout 15초).
// API가 한 번 응답하기 전까지는 넉넉히 기다리고, 그 뒤로는 짧게 끊되 한 번 더 시도한 다음에 전환한다.
const COLD_TIMEOUT_MS = 20000;
const WARM_TIMEOUT_MS = 8000;
let apiWarm = false;
const apiTimeout = () => (apiWarm ? WARM_TIMEOUT_MS : COLD_TIMEOUT_MS);

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

const isNotFound = (e: unknown) => (e as { status?: number }).status === 404;

/** API에서 받는다. 404는 그대로 던지고, 네트워크·서버 오류면 한 번 더 시도한 뒤 정적 번들로 전환하고 null */
async function fromApi<T>(apiPath: string): Promise<T | null> {
  const url = `${config.apiBase}${apiPath}`;
  for (let attempt = 0; ; attempt++) {
    try {
      const data = await fetchJson<T>(url, attempt ? COLD_TIMEOUT_MS : apiTimeout());
      apiWarm = true;
      return data;
    } catch (e) {
      if (isNotFound(e)) throw e;
      if (attempt === 0 && apiWarm) continue;   // 잠깐 끊긴 것일 수 있다. 처음(잠에서 깨는 중)은 이미 오래 기다렸다
      console.warn("API 응답 없음 → 정적 번들로 전환합니다:", (e as Error).message);
      markApiDown();
      return null;
    }
  }
}

/** 정적 번들은 일부 지역만 들어 있다. API가 안 될 때 백업에 없는 문서는 "없음"(404)이 아니라 "연결 지연"으로 알린다 */
export class ApiUnavailableError extends Error {
  readonly unavailable = true;
  constructor() {
    super("서버(API) 응답이 늦어 이 데이터를 받지 못했습니다. 백업 데이터에는 일부 지역만 들어 있습니다.");
  }
}
export const isApiUnavailable = (e: unknown) => e instanceof ApiUnavailableError;

async function fromStatic<T>(staticPath: string): Promise<T> {
  try {
    return await fetchJson<T>(`${config.dataBase}/${staticPath}`);
  } catch (e) {
    if (config.apiBase && isNotFound(e)) throw new ApiUnavailableError();
    throw e;
  }
}

/** apiPath: API 경로(/meta 등), staticPath: 정적 번들 상대경로(meta.json 등) */
async function get<T>(apiPath: string, staticPath: string): Promise<T> {
  if (source === "api") {
    const data = await fromApi<T>(apiPath);
    if (data !== null) return data;
  }
  return fromStatic<T>(staticPath);
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
      const d = await fromApi<Detail>(`/points/${key}`);
      if (d !== null) return d;
    } catch (e) {
      if (isNotFound(e)) return null;
      throw e;
    }
  }
  const idx = await fromStatic<KeyIndexDoc>("key_index.json");
  const rid = idx[key];
  if (!rid) {
    if (config.apiBase) throw new ApiUnavailableError();
    return null;
  }
  return (await fromStatic<DetailDoc>(`detail/${rid}.json`))[key] ?? null;
}

/** GPS 좌표 → 가장 가까운 지역 (#18). API가 없으면 regions.json 중심점 중 가장 가까운 곳 */
export async function nearestRegion(lat: number, lng: number, regions: RegionsDoc): Promise<string | null> {
  if (source === "api") {
    try {
      const r = await fetchJson<{ region_id: string }>(
        `${config.apiBase}/nearest?lat=${lat}&lng=${lng}`, apiTimeout());
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
      const r = await fetchJson<{ hits: SearchHit[] }>(`${config.apiBase}/search?${params}`, apiTimeout());
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
