// 구글(Google Identity Services)·네이버(네이버 아이디로 로그인 JS SDK) 연동.
// 정적 초안이라 브라우저에서 받은 프로필을 그대로 쓴다. 실서비스에서는 받은 토큰을 backend에서 검증해야 한다.
import { GOOGLE_CLIENT_ID, NAVER_CLIENT_ID, NAVER_CALLBACK_URL } from "./oauth-config.js";

const GOOGLE_SDK = "https://accounts.google.com/gsi/client";
const NAVER_SDK = "https://static.nid.naver.com/js/naveridlogin_js_sdk_2.0.2.js";

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src;
    el.onload = resolve;
    el.onerror = () => reject(new Error(`${src} 를 불러오지 못했습니다(인터넷 연결 확인).`));
    document.head.append(el);
  });
}

// JWT(구글 credential) 본문 디코드 — 서명 검증은 하지 않는다(초안용)
function decodeJwt(token) {
  const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  const json = decodeURIComponent([...atob(b64)].map((c) => `%${c.charCodeAt(0).toString(16).padStart(2, "0")}`).join(""));
  return JSON.parse(json);
}

export const googleConfigured = () => !!GOOGLE_CLIENT_ID;
export const naverConfigured = () => !!NAVER_CLIENT_ID;

// 구글 공식 버튼을 container에 그린다. 로그인되면 onProfile({provider, sub, name, email})
export async function setupGoogle(container, onProfile, onError) {
  await loadScript(GOOGLE_SDK);
  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: (resp) => {
      try {
        const p = decodeJwt(resp.credential);
        onProfile({ provider: "google", sub: p.sub, name: p.name, email: p.email });
      } catch (e) { onError(e); }
    },
  });
  container.innerHTML = "";
  google.accounts.id.renderButton(container, {
    theme: "outline", size: "large", shape: "rectangular", text: "signin_with", locale: "ko",
    width: Math.min(container.clientWidth || 294, 400),
  });
}

// 네이버 SDK 초기화. 반환값 start()를 누르면 네이버 로그인 페이지로 이동하고,
// 로그인 후 NAVER_CALLBACK_URL(이 intro.html)로 돌아오면 onProfile이 호출된다.
export async function setupNaver(onProfile, onError) {
  await loadScript(NAVER_SDK);
  let holder = document.getElementById("naverIdLogin");
  if (!holder) {
    holder = Object.assign(document.createElement("div"), { id: "naverIdLogin", hidden: true });
    document.body.append(holder);
  }
  const naverLogin = new naver.LoginWithNaverId({
    clientId: NAVER_CLIENT_ID, callbackUrl: NAVER_CALLBACK_URL, isPopup: false,
    loginButton: { color: "green", type: 1, height: 40 },
  });
  naverLogin.init();

  if (location.hash.includes("access_token")) {
    naverLogin.getLoginStatus((ok) => {
      history.replaceState(null, "", location.pathname + location.search);
      if (!ok) return onError(new Error("네이버 로그인 정보를 가져오지 못했습니다."));
      const u = naverLogin.user;
      onProfile({ provider: "naver", sub: u.getId(), name: u.getName?.() || u.getNickName?.(), email: u.getEmail?.() });
    });
  } else if (location.hash.includes("error")) {
    history.replaceState(null, "", location.pathname + location.search);
    onError(new Error("네이버 로그인이 취소되었습니다."));
  }
  return () => document.querySelector("#naverIdLogin_loginButton")?.click();
}
