"use client";
// 인트로 로그인 카드 (web-draft intro.html 흐름 이식, docs/requests.md #19):
// 구글(GIS)·네이버 SDK로 받은 토큰을 API가 검증 → 처음이면 사는 지역 선택 → 지도.

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { config } from "@/lib/config";
import { devLoginAvailable, loginDev, loginGoogle, loginGuest, loginNaver, saveRegion } from "@/lib/auth";
import { useRegions } from "@/lib/queries";

declare global {
  interface Window {
    google?: any; // eslint-disable-line @typescript-eslint/no-explicit-any
    naver?: any; // eslint-disable-line @typescript-eslint/no-explicit-any
  }
}

// 같은 주소는 한 Promise를 공유한다. 태그가 있다고 바로 resolve하면 로딩 전에 SDK를 쓰게 됨(개발 모드 effect 2회 실행)
const scripts = new Map<string, Promise<void>>();
function loadScript(src: string) {
  let p = scripts.get(src);
  if (!p) {
    p = new Promise<void>((resolve, reject) => {
      const el = Object.assign(document.createElement("script"), { src, async: true });
      el.onload = () => resolve();
      el.onerror = () => {
        scripts.delete(src);
        el.remove();
        reject(new Error(`${src}를 불러오지 못했습니다(인터넷 연결 확인).`));
      };
      document.head.append(el);
    });
    scripts.set(src, p);
  }
  return p;
}

export function LoginCard() {
  const router = useRouter();
  const [step, setStep] = useState<"main" | "region">("main");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const devVisible = useSyncExternalStore(() => () => {}, devLoginAvailable, () => false);
  const googleRef = useRef<HTMLDivElement>(null);
  const naverStart = useRef<(() => void) | null>(null);

  const goMap = () => router.replace("/map");
  const after = ({ needsRegion }: { needsRegion: boolean }) => (needsRegion ? setStep("region") : goMap());
  const run = async (fn: () => Promise<{ needsRegion: boolean }>) => {
    setBusy(true);
    setMsg("");
    try {
      after(await fn());
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // 구글 공식 버튼
  useEffect(() => {
    if (!config.googleClientId) return;
    loadScript("https://accounts.google.com/gsi/client").then(() => {
      window.google.accounts.id.initialize({
        client_id: config.googleClientId,
        callback: (resp: { credential: string }) => run(() => loginGoogle(resp.credential)),
      });
      if (googleRef.current) {
        googleRef.current.innerHTML = "";
        window.google.accounts.id.renderButton(googleRef.current, {
          theme: "outline", size: "large", text: "signin_with", locale: "ko", width: 294,
        });
      }
    }).catch((e) => setMsg(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 네이버: 로그인 후 이 페이지(#access_token=...)로 돌아온다
  useEffect(() => {
    if (!config.naverClientId) return;
    loadScript("https://static.nid.naver.com/js/naveridlogin_js_sdk_2.0.2.js").then(() => {
      let holder = document.getElementById("naverIdLogin");
      if (!holder) {
        holder = Object.assign(document.createElement("div"), { id: "naverIdLogin", hidden: true });
        document.body.append(holder);
      }
      const nl = new window.naver.LoginWithNaverId({
        clientId: config.naverClientId, callbackUrl: `${location.origin}/`, isPopup: false,
        loginButton: { color: "green", type: 1, height: 40 },
      });
      nl.init();
      naverStart.current = () => (document.querySelector("#naverIdLogin_loginButton") as HTMLElement | null)?.click();
      if (location.hash.includes("access_token")) {
        const token = new URLSearchParams(location.hash.slice(1)).get("access_token");
        history.replaceState(null, "", location.pathname + location.search);
        if (token) run(() => loginNaver(token));
      } else if (location.hash.includes("error")) {
        history.replaceState(null, "", location.pathname + location.search);
        setMsg("네이버 로그인이 취소되었습니다.");
      }
    }).catch((e) => setMsg(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const notReady = (name: string, env: string) => () =>
    setMsg(`${name} 로그인은 아직 설정 전입니다. frontend/.env.local에 ${env}를 넣어 주세요.`);

  if (step === "region") return <RegionStep onDone={goMap} onCancel={() => setStep("main")} />;

  return (
    <section className="auth-card" aria-label="로그인">
      <p className="card-title">간편 로그인</p>
      <div className="social">
        <div ref={googleRef} className="social-slot">
          {!config.googleClientId && (
            <button type="button" className="social-btn google" onClick={notReady("구글", "NEXT_PUBLIC_GOOGLE_CLIENT_ID")}>
              <GoogleMark /> 구글 아이디로 로그인
            </button>
          )}
        </div>
        <button type="button" className="social-btn naver" disabled={busy}
          onClick={config.naverClientId ? () => naverStart.current?.() : notReady("네이버", "NEXT_PUBLIC_NAVER_CLIENT_ID")}>
          <span className="naver-n" aria-hidden="true">N</span> 네이버 아이디로 로그인
        </button>
      </div>
      <p className="msg" role="alert">{msg}</p>
      <div className="divider"><span>또는</span></div>
      <button type="button" className="ghost" onClick={() => { loginGuest(); goMap(); }}>비회원으로 바로 이용하기</button>
      <p className="guest-note">비회원은 지도를 볼 수 있지만 리뷰·평가·이벤트에는 참여할 수 없습니다.</p>
      {devVisible && (
        <button type="button" className="dev-login" disabled={busy} onClick={() => run(loginDev)}>
          개발용 로그인 (로컬 전용)
        </button>
      )}
    </section>
  );
}

function RegionStep({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const { data: regions, error } = useRegions();
  const [sido, setSido] = useState("");
  const [rid, setRid] = useState("");
  const [msg, setMsg] = useState("");
  const sidos = useMemo(() => [...new Map((regions?.regions ?? []).map((r) => [r.sido_code, r.sido])).entries()]
    .sort((a, b) => a[0].localeCompare(b[0])), [regions]);
  const sggs = useMemo(() => (regions?.regions ?? []).filter((r) => r.sido_code === sido)
    .sort((a, b) => a.sigungu.localeCompare(b.sigungu, "ko")), [regions, sido]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sido) return setMsg("사는 지역(시도)을 선택하세요.");
    const r = sggs.find((x) => x.region_id === rid);
    try {
      await saveRegion(r ? { region_id: r.region_id, sido: r.sido, sigungu: r.sigungu }
        : { sido_code: sido, sido: sidos.find(([c]) => c === sido)?.[1] ?? "" });
      onDone();
    } catch (err) {
      setMsg((err as Error).message);
    }
  };

  return (
    <section className="auth-card" aria-label="사는 지역">
    <form id="step-region" onSubmit={submit} noValidate>
      <p className="card-title">거의 다 됐어요!</p>
      <p className="welcome">사는 지역을 알려 주시면 내 동네 지도부터 보여 드려요.</p>
      {error && <p className="msg">지역 목록을 불러오지 못했습니다.</p>}
      <div className="row">
        <label>사는 지역 (시도)
          <select value={sido} onChange={(e) => { setSido(e.target.value); setRid(""); }} required>
            <option value="">선택하세요</option>
            {sidos.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </label>
        <label>시군구
          <select value={rid} onChange={(e) => setRid(e.target.value)} disabled={!sggs.length}>
            <option value="">{sido ? "선택 안 함" : "시도를 먼저 고르세요"}</option>
            {sggs.map((r) => <option key={r.region_id} value={r.region_id}>{r.sigungu}</option>)}
          </select>
        </label>
      </div>
      <p className="msg" role="alert">{msg}</p>
      <button type="submit" className="primary">가입 완료하고 시작하기</button>
      <button type="button" className="link" onClick={onCancel}>다른 방법으로 로그인</button>
    </form>
    </section>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.7c4.3-4 6.9-9.9 6.9-17.1z" />
      <path fill="#FBBC05" d="M10.6 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.7l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.7c-2.1 1.4-4.8 2.3-8.5 2.3-6.2 0-11.5-4.1-13.4-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z" />
    </svg>
  );
}
