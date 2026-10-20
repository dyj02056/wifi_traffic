// 로그인 상태 (docs/requests.md #19): 구글·네이버(서버 검증 → Neon 회원) + 비회원 + 로컬 전용 개발용 로그인.
// 브라우저에는 서버가 발급한 세션 토큰과 표시용 회원 정보만 둔다. 비밀번호는 다루지 않는다.
"use client";

import { useSyncExternalStore } from "react";
import { config, isLocalHost } from "./config";

export interface User {
  id: number;
  provider: "google" | "naver" | "dev";
  display_name: string;
  sido: string | null;
  sigungu: string | null;
  region_id: string | null;
}

export type Session =
  | { type: "guest" }
  | { type: "member"; token: string | null; user: User };   // token null = API 없이 로컬에서만 만든 개발용 회원

interface AuthResponse {
  token: string;
  user: User;
  needs_region: boolean;
}

const KEY = "wt_session_v2";
const listeners = new Set<() => void>();

function read(): Session | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "null");
  } catch {
    return null;
  }
}

let cached: Session | null | undefined;
function snapshot(): Session | null {
  if (cached === undefined) cached = read();
  return cached;
}

function write(s: Session | null) {
  try {
    if (s) localStorage.setItem(KEY, JSON.stringify(s));
    else localStorage.removeItem(KEY);
  } catch {
    /* 저장소를 못 쓰면 이번 탭에서만 유지 */
  }
  cached = s;
  listeners.forEach((fn) => fn());
}

/** 로그인 상태 훅. 서버 렌더링 중에는 undefined(아직 모름) */
export function useSession(): Session | null | undefined {
  return useSyncExternalStore(
    (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    snapshot,
    () => undefined,
  );
}

export const loginGuest = () => write({ type: "guest" });
export const logout = () => write(null);

async function post(path: string, body?: unknown, token?: string, method = "POST"): Promise<Response> {
  return fetch(`${config.apiBase}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function finish(res: Response): Promise<{ needsRegion: boolean }> {
  if (!res.ok) {
    const msg = await res.json().then((d) => d.detail).catch(() => null);
    throw new Error(msg || `로그인에 실패했습니다 (${res.status})`);
  }
  const data = (await res.json()) as AuthResponse;
  write({ type: "member", token: data.token, user: data.user });
  return { needsRegion: data.needs_region };
}

export async function loginGoogle(credential: string) {
  if (!config.apiBase) throw new Error("API 주소(NEXT_PUBLIC_API_BASE)가 없어 로그인할 수 없습니다");
  return finish(await post("/auth/google", { credential }));
}

export async function loginNaver(accessToken: string) {
  if (!config.apiBase) throw new Error("API 주소(NEXT_PUBLIC_API_BASE)가 없어 로그인할 수 없습니다");
  return finish(await post("/auth/naver", { access_token: accessToken }));
}

export const devLoginAvailable = isLocalHost;

/** 로컬 전용. API(DEV_LOGIN=1, DB)가 있으면 서버 회원으로, 없으면 이 브라우저에서만 쓰는 회원으로 */
export async function loginDev() {
  if (!isLocalHost()) throw new Error("개발용 로그인은 로컬에서만 쓸 수 있습니다");
  if (config.apiBase) {
    try {
      return await finish(await post("/auth/dev"));
    } catch (e) {
      console.warn("API 개발용 로그인 실패 → 로컬 회원으로 진행:", (e as Error).message);
    }
  }
  const prev = read();
  const user: User = prev?.type === "member" && prev.user.provider === "dev" ? prev.user
    : { id: 0, provider: "dev", display_name: "개발자", sido: null, sigungu: null, region_id: null };
  write({ type: "member", token: null, user });
  return { needsRegion: !user.sido };
}

/** 사는 지역 저장. region = 시군구를 고르면 region_id, 시도만 고르면 sido_code */
export async function saveRegion(sel: { region_id?: string; sido_code?: string; sido: string; sigungu?: string }) {
  const s = read();
  if (s?.type !== "member") throw new Error("로그인이 필요합니다");
  if (s.token && config.apiBase) {
    const res = await post("/me/region", { region_id: sel.region_id ?? null, sido_code: sel.sido_code ?? null },
      s.token, "PUT");
    if (!res.ok) throw new Error(`지역을 저장하지 못했습니다 (${res.status})`);
    write({ ...s, user: (await res.json()) as User });
    return;
  }
  write({ ...s, user: { ...s.user, sido: sel.sido, sigungu: sel.sigungu ?? null, region_id: sel.region_id ?? null } });
}

export const PROVIDER_LABEL: Record<User["provider"], string> = { google: "구글", naver: "네이버", dev: "개발용" };
