// 데이터 접근 (plan.md §6.1 경로 표, docs/requests.md #16).
// 우리 API(NEXT_PUBLIC_API_BASE)를 먼저 쓰고, 응답이 없으면 정적 번들(/data)로 자동 전환한다(시연 백업).
//
// [이 파일이 하는 일]
//   화면이 필요한 데이터(지점 목록, 지점 상세, 채점 규칙 등)를 받아 오는 창구입니다.
//   두 군데에서 받을 수 있습니다.
//     1) API 서버: 인터넷에 올린 백엔드. 전국 데이터가 있고 매일 갱신된다.
//     2) 정적 번들(/data 폴더): 사이트와 함께 올려 둔 JSON 파일. 일부 지역만 들어 있는 '백업'이다.
//   평소엔 API를 쓰다가, API가 응답하지 않으면 자동으로 정적 번들로 바꾸고, 5분 뒤 다시 API를 시도합니다.
//   화면 쪽 코드는 이 파일의 getMeta(), getPoints() 같은 함수만 부르면 되고, 어디서 받는지는 신경 쓰지 않아도 됩니다.
import { config } from "./config";
import type {
  BackgroundDoc, CasesDoc, ChangesDoc, Detail, DetailDoc, KeyIndexDoc, MetaDoc, PointsDoc, RegionsDoc, RulesDoc,
  SensitivityDoc,
} from "./types";

// 지금 데이터를 받는 곳: "api"(서버) 또는 "static"(정적 백업 파일)
export type DataSource = "api" | "static";

// API가 응답하지 않으면 5분 동안은 페이지를 옮겨도 바로 정적 번들을 쓴다(매번 연결 실패를 기다리지 않게).
// 5분이 지나면 다시 API로 돌아간다(새로고침하지 않아도).
const DOWN_KEY = "wt_api_down_until";
const DOWN_MS = 5 * 60 * 1000;
// "API가 언제까지 쉬는 중인지" 시각을 sessionStorage(브라우저 탭이 열려 있는 동안 기억하는 저장소)에 보관한다
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

// 처음 시작할 때: API 주소가 설정돼 있고 쉬는 시간이 지났으면 API, 아니면 정적 번들
let source: DataSource = config.apiBase && downUntil() <= Date.now() ? "api" : "static";
// 데이터 출처가 바뀌면 알려 줄 대상 목록(화면의 '백업 데이터 사용 중' 표시 등이 여기에 등록한다)
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

// at 시각에 API로 돌아가도록 예약한다(이미 예약된 것이 있으면 취소하고 새로 예약)
let recoverTimer: ReturnType<typeof setTimeout> | undefined;
function scheduleRecover(at: number) {
  clearTimeout(recoverTimer);
  recoverTimer = setTimeout(retryApi, Math.max(0, at - Date.now()));
}
// API가 응답하지 않을 때: 5분간 쉬는 것으로 기록하고, 5분 뒤 복귀를 예약하고, 정적 번들로 바꾼다
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

// 주소에서 JSON을 받아 온다. timeoutMs가 지나도 답이 없으면 요청을 중단(abort)한다.
// 응답 코드가 200번대가 아니면(예: 404 없음, 500 서버 오류) status를 붙인 오류를 던진다.
// <T>는 '돌려줄 데이터의 모양'을 부르는 쪽에서 정한다는 TypeScript 표기다.
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

// 정적 번들 파일에서 받는다. API를 쓰는 사이트인데 백업에 그 파일이 없으면 '연결 지연' 오류로 바꿔 알린다
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

// 문서별로 받는 함수들 (rid = region_id, 지역 번호. 예: "41-goyang")
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
  // 근사 계산: 데이터가 있는 지역들의 중심점 중 내 위치와 가장 가까운 곳을 고른다
  // (경도 차이에 cos(위도)를 곱하는 이유: 위도가 높을수록 경도 1도의 실제 거리가 짧아지기 때문)
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

// 장소 검색 결과 한 건
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
  // API가 안 될 때: 검색어를 띄어쓰기로 나눠, 단어가 모두 이름에 들어 있는 지점을 최대 15개 찾는다
  const toks = q.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = localPoints
    .filter((p) => toks.every((t) => p.name.toLowerCase().includes(t)))
    .slice(0, 15)
    .map((p) => ({ key: p.key, region_id: regionId ?? "", sido: region?.sido ?? "", sigungu: region?.sigungu ?? "",
      name: p.name, address: null, place_detail: null, lat: p.lat, lng: p.lng }));
  return { hits, scope: "지금 지역" };
}
