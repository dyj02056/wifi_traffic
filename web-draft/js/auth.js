// 인트로 화면의 회원가입·로그인·비회원 이용 (정적 초안용).
// 서버가 없으므로 계정은 이 브라우저의 localStorage에만 저장된다. 비밀번호는 salt + SHA-256 해시로만 보관.
// 실제 서비스에서는 backend 인증 API로 바꿔야 한다.

const USERS_KEY = "wt_users";
const SESSION_KEY = "wt_session";

export const SIDO_LIST = [
  "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",
  "경기도", "강원특별자치도", "충청북도", "충청남도", "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
];

function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
}

async function hash(password, salt) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${salt}:${password}`));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const ID_RE = /^[a-zA-Z0-9_]{4,20}$/;

export async function signup({ id, password, sido, sigungu }) {
  id = id.trim();
  if (!ID_RE.test(id)) throw new Error("아이디는 영문·숫자·밑줄 4~20자로 입력하세요.");
  if (password.length < 6) throw new Error("비밀번호는 6자 이상이어야 합니다.");
  if (!sido) throw new Error("사는 지역(시도)을 선택하세요.");
  const users = load(USERS_KEY, {});
  if (users[id.toLowerCase()]) throw new Error("이미 사용 중인 아이디입니다.");
  const salt = crypto.getRandomValues(new Uint32Array(2)).join("");
  users[id.toLowerCase()] = { id, salt, hash: await hash(password, salt), sido, sigungu: sigungu.trim(), created_at: new Date().toISOString() };
  if (!save(USERS_KEY, users)) throw new Error("이 브라우저에서는 저장소를 쓸 수 없어 가입할 수 없습니다.");
}

export async function login(id, password) {
  const user = load(USERS_KEY, {})[id.trim().toLowerCase()];
  if (!user || (await hash(password, user.salt)) !== user.hash) throw new Error("아이디 또는 비밀번호가 올바르지 않습니다.");
  save(SESSION_KEY, { type: "member", id: user.id, sido: user.sido, sigungu: user.sigungu });
}

// 구글·네이버 연동 로그인. profile = { provider: "google"|"naver", sub, name, email }
// 이미 연동된 계정이면 바로 로그인하고 true, 처음이면 지역 입력이 필요하므로 false (pending에 보관).
const PENDING_KEY = "wt_social_pending";
const PROVIDER_LABEL = { google: "구글", naver: "네이버" };

export function socialLogin(profile) {
  const key = `${profile.provider}:${profile.sub}`;
  const user = load(USERS_KEY, {})[key];
  if (user) {
    save(SESSION_KEY, { type: "member", id: user.id, provider: user.provider, sido: user.sido, sigungu: user.sigungu });
    return true;
  }
  save(PENDING_KEY, profile);
  return false;
}

export function pendingSocial() {
  return load(PENDING_KEY, null);
}

export function cancelSocialSignup() {
  try { localStorage.removeItem(PENDING_KEY); } catch { /* 무시 */ }
}

export function completeSocialSignup({ sido, sigungu }) {
  const p = pendingSocial();
  if (!p) throw new Error("연동 정보가 없습니다. 다시 로그인해 주세요.");
  if (!sido) throw new Error("사는 지역(시도)을 선택하세요.");
  const users = load(USERS_KEY, {});
  const id = p.name || p.email || `${PROVIDER_LABEL[p.provider]} 사용자`;
  users[`${p.provider}:${p.sub}`] = { id, provider: p.provider, email: p.email ?? null, sido, sigungu: sigungu.trim(),
    created_at: new Date().toISOString() };
  if (!save(USERS_KEY, users)) throw new Error("이 브라우저에서는 저장소를 쓸 수 없어 가입할 수 없습니다.");
  try { localStorage.removeItem(PENDING_KEY); } catch { /* 무시 */ }
  socialLogin(p);
}

export function loginGuest() {
  save(SESSION_KEY, { type: "guest" });
}

export function logout() {
  try { localStorage.removeItem(SESSION_KEY); } catch { /* 무시 */ }
}

export function getSession() {
  return load(SESSION_KEY, null);
}

// 리뷰·평가·이벤트 참여 가능 여부 — 회원만 true
export function canParticipate() {
  return getSession()?.type === "member";
}

// 지도·채점 기준 등 앱 화면에서 호출: 세션이 없으면 인트로로 보내고, 상단 내비에 사용자 상태를 붙인다.
export function requireSession(nav = document.querySelector(".top-nav .nav-right") ?? document.querySelector(".top-nav")) {
  const s = getSession();
  if (!s) { location.replace("intro.html" + location.search); return null; }
  if (nav) {
    const box = document.createElement("span");
    box.className = "user-box";
    const label = document.createElement("span");
    label.className = s.type === "member" ? "user-name" : "badge guest";
    label.textContent = s.type === "member"
      ? `${s.provider ? `[${PROVIDER_LABEL[s.provider]}] ` : ""}${s.id} 님 (${s.sigungu ? `${s.sido} ${s.sigungu}` : s.sido})` : "비회원";
    if (s.type === "guest") label.title = "비회원은 리뷰·평가·이벤트에 참여할 수 없습니다";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = s.type === "member" ? "로그아웃" : "로그인/회원가입";
    btn.addEventListener("click", () => { logout(); location.href = "intro.html" + location.search; });
    box.append(label, btn);
    nav.append(box);
  }
  return s;
}
