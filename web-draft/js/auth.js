// 인트로 화면의 구글·네이버 로그인과 비회원 이용 (정적 초안용). 아이디·비밀번호 가입은 두지 않는다(requests #19).
// 서버가 없으므로 회원 정보(제공자·표시이름·사는 지역)는 이 브라우저의 localStorage에만 저장된다.
// 실제 서비스에서는 backend 인증 API + Neon 회원 테이블로 바꿔야 한다.
//
// [이 파일이 하는 일]
//   로그인 상태(회원/비회원)와 '가입한 회원 목록'을 브라우저 저장소(localStorage)에 넣고 꺼냅니다.
//   흐름: 구글·네이버 로그인 → 처음이면 지역 입력 대기(pending) → 지역 입력 완료 → 회원 저장·로그인 상태 시작.
//   지도 등 앱 화면은 requireSession()을 불러, 로그인하지 않았으면 인트로 화면으로 돌려보냅니다.
//   (frontend는 이 대신 서버가 확인하는 방식(lib/auth.ts)을 쓴다)

const USERS_KEY = "wt_users";       // 가입한 회원 목록
const SESSION_KEY = "wt_session";   // 지금 로그인 상태

// localStorage 읽기·쓰기 도우미. 저장소를 못 쓰는 환경(사생활 보호 모드 등)에서도 오류로 멈추지 않게 감싼다
function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
}

// 구글·네이버 연동 로그인. profile = { provider: "google"|"naver"|"dev", sub, name, email }
// 이미 연동된 계정이면 바로 로그인하고 true, 처음이면 지역 입력이 필요하므로 false (pending에 보관).
const PENDING_KEY = "wt_social_pending";
const PROVIDER_LABEL = { google: "구글", naver: "네이버", dev: "개발용" };

// 개발용 가짜 로그인은 로컬 개발 주소에서만 보여 준다. 배포 주소에서는 버튼이 생기지 않는다.
export const devLoginAvailable = () => ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
export const DEV_PROFILE = { provider: "dev", sub: "local-dev", name: "개발자", email: null };

// 회원 정보로 로그인 상태를 시작한다
function startSession(user) {
  save(SESSION_KEY, { type: "member", id: user.id, provider: user.provider, sido: user.sido, sigungu: user.sigungu,
    region_id: user.region_id ?? null });
}

export function socialLogin(profile) {
  if (profile.provider === "dev" && !devLoginAvailable()) throw new Error("개발용 로그인은 로컬에서만 쓸 수 있습니다.");
  const user = load(USERS_KEY, {})[`${profile.provider}:${profile.sub}`];
  if (user) {
    startSession(user);
    return true;
  }
  save(PENDING_KEY, profile);
  return false;
}

// 지역 입력을 기다리는 중인 로그인 정보(없으면 null) / 가입 취소
export function pendingSocial() {
  return load(PENDING_KEY, null);
}

export function cancelSocialSignup() {
  try { localStorage.removeItem(PENDING_KEY); } catch { /* 무시 */ }
}

// region = regions.json의 시군구 하나({region_id, sido, sigungu}) 또는 시도만 고른 경우 {region_id: null, sido, sigungu: ""}
export function completeSocialSignup({ region_id = null, sido, sigungu = "" }) {
  const p = pendingSocial();
  if (!p) throw new Error("연동 정보가 없습니다. 다시 로그인해 주세요.");
  if (!sido) throw new Error("사는 지역(시도)을 선택하세요.");
  const users = load(USERS_KEY, {});
  const id = p.name || p.email || `${PROVIDER_LABEL[p.provider]} 사용자`;
  users[`${p.provider}:${p.sub}`] = { id, provider: p.provider, email: p.email ?? null, sido, sigungu, region_id,
    created_at: new Date().toISOString() };
  if (!save(USERS_KEY, users)) throw new Error("이 브라우저에서는 저장소를 쓸 수 없어 가입할 수 없습니다.");
  try { localStorage.removeItem(PENDING_KEY); } catch { /* 무시 */ }
  socialLogin(p);
}

// 비회원으로 시작 / 로그아웃 / 지금 로그인 상태 읽기
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
