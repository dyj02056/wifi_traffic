// 번들 fetch. DATA_BASE 하나로 실데이터(./data)와 mock(./mock)을 전환한다.
// 주소창에 ?data=mock 을 붙이면 mock, 없으면 ./data. ./data가 비어 있으면 mock으로 자동 전환(배지 표시됨).
// (scripts/sync_bundle이 backend/dist/data → web-draft/data, contracts/mock → web-draft/mock 으로 복사)
//
// [이 파일이 하는 일]
//   web-draft(정적 초안: 서버 없이 HTML·JS 파일만으로 도는 시안이자 인터넷 없는 시연용 백업 화면)가
//   쓰는 데이터를 JSON 파일에서 읽어 오는 창구입니다. 한 번 읽은 파일은 기억(cache)해 두고 다시 쓰고,
//   읽기에 실패하면 기억에서 지워 다음에 다시 시도할 수 있게 합니다.
//   (frontend의 lib/api.ts와 같은 역할이지만 API 서버는 쓰지 않는다)

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

// 시작할 때 한 번 부른다: meta.json을 읽어 보고, 실데이터가 없으면 mock 폴더로 바꿔 다시 읽는다
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

// 지점 하나의 상세: key_index로 어느 지역 파일에 있는지 찾은 뒤 그 지역 상세 파일에서 꺼낸다
export async function getDetail(key) {
  const idx = await getKeyIndex();
  const rid = idx[key];
  if (!rid) return null;
  return (await getDetailMap(rid))[key] ?? null;
}
