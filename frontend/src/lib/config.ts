// 환경변수 (.env.local.example 참고). NEXT_PUBLIC_* 는 브라우저에 노출되는 값이므로 비밀키를 넣지 않는다.
export const config = {
  /** 우리 API (예: http://localhost:8000/api). 비우면 정적 번들만 쓴다. */
  apiBase: (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, ""),
  /** 정적 번들 경로: /data(실데이터, scripts/sync_bundle.sh가 복사) 또는 /mock */
  dataBase: (process.env.NEXT_PUBLIC_DATA_BASE ?? "/data").replace(/\/$/, ""),
  kakaoJsKey: process.env.NEXT_PUBLIC_KAKAO_JS_KEY ?? "",
  googleClientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "",
  naverClientId: process.env.NEXT_PUBLIC_NAVER_CLIENT_ID ?? "",
};

export const isLocalHost = () =>
  typeof window !== "undefined" && ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
