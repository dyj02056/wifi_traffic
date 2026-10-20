// 번들 fetch. DATA_BASE 하나로 실데이터(./data)와 mock(./mock)을 전환한다.
// 주소창에 ?data=mock 을 붙이면 mock, 없으면 ./data. ./data가 비어 있으면 mock으로 자동 전환(배지 표시됨).
// (scripts/sync_bundle이 backend/dist/data → web-draft/data, contracts/mock → web-draft/mock 으로 복사)

const params = new URLSearchParams(location.search);
const BASES = { real: "./data", mock: "./mock" };
let DATA_BASE = params.get("data") === "mock" ? BASES.mock : BASES.real;

const cache = new Map();

async function getJSON(path) {
  const url = `${DATA_BASE}/${path}`;
  if (cache.has(url)) return cache.get(url);
  const p = fetch(url).then((res) => {
    if (!res.ok) throw new Error(`${res.status} ${url}`);
    return res.json();
  });
  cache.set(url, p);
  try {
    return await p;
  } catch (e) {
    cache.delete(url);
    throw e;
  }
}

export async function init() {
  try {
    return await getJSON("meta.json");
  } catch (e) {
    if (DATA_BASE === BASES.mock) throw e;
    console.warn("실데이터 번들이 없어 mock으로 전환합니다:", e.message);
    DATA_BASE = BASES.mock;
    return getJSON("meta.json");
  }
}

export const dataBase = () => DATA_BASE;
export const getMeta = () => getJSON("meta.json");
export const getRules = () => getJSON("rules.json");
export const getRegions = () => getJSON("regions.json");
export const getKeyIndex = () => getJSON("key_index.json");
export const getPoints = (rid) => getJSON(`points/${rid}.json`);
export const getDetailMap = (rid) => getJSON(`detail/${rid}.json`);
export const getChanges = (rid) => getJSON(`changes/${rid}.json`);
export const getSensitivity = (rid) => getJSON(`sensitivity/${rid}.json`);
export const getBackground = () => getJSON("background.json");
export const getCases = () => getJSON("cases.json");

export async function getDetail(key) {
  const idx = await getKeyIndex();
  const rid = idx[key];
  if (!rid) return null;
  return (await getDetailMap(rid))[key] ?? null;
}
