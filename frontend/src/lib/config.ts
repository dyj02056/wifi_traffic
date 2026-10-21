// 환경변수 (.env.local.example 참고). NEXT_PUBLIC_* 는 브라우저에 노출되는 값이므로 비밀키를 넣지 않는다.
//
// [이 파일이 하는 일]
//   사이트 설정값(API 주소, 지도 키, 로그인 앱 ID)을 한곳에 모읍니다.
//   값은 코드에 직접 쓰지 않고 '환경변수'(frontend/.env.local 파일이나 배포 서비스 설정)에서 읽어서,
//   개발용·배포용 주소를 코드 수정 없이 바꿀 수 있게 합니다.
//   replace(/\/$/, "")는 주소 끝의 '/'를 떼어 내 나중에 "/meta" 등을 붙일 때 '//'가 되지 않게 합니다.
export const config = {
  /** 우리 API (예: http://localhost:8000/api). 비우면 정적 번들만 쓴다. */
  apiBase: (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, ""),
  /** 정적 번들 경로: /data(실데이터, scripts/sync_bundle.sh가 복사) 또는 /mock */
  dataBase: (process.env.NEXT_PUBLIC_DATA_BASE ?? "/data").replace(/\/$/, ""),
  /** 카카오맵 JavaScript 키 (지도·장소 검색). 비우면 지도를 그리지 않는다 */
  kakaoJsKey: process.env.NEXT_PUBLIC_KAKAO_JS_KEY ?? "",
  /** 구글 로그인 앱 ID (공개해도 되는 값) */
  googleClientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "",
  /** 네이버 로그인 앱 ID (공개해도 되는 값) */
  naverClientId: process.env.NEXT_PUBLIC_NAVER_CLIENT_ID ?? "",
};

/** 지금 내 컴퓨터(로컬 개발 환경)에서 열었는지. 개발용 로그인은 이때만 보인다 */
export const isLocalHost = () =>
  typeof window !== "undefined" && ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
