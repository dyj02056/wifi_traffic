// 구글·네이버 로그인 설정. 클라이언트 ID는 공개돼도 되는 값이지만, 비밀키(Client Secret)는 절대 여기에 넣지 않는다.
// 비어 있으면 해당 버튼은 "설정 전" 안내만 띄운다.
//
// 구글: https://console.cloud.google.com/apis/credentials → OAuth 클라이언트 ID(웹 애플리케이션)
//   "승인된 자바스크립트 원본"에 http://localhost:5501 (배포 주소도) 추가
// 네이버: https://developers.naver.com/apps → 애플리케이션 등록, 사용 API "네이버 로그인"(이름·이메일 동의)
//   서비스 URL http://localhost:5501, Callback URL은 아래 NAVER_CALLBACK_URL과 똑같이 등록
export const GOOGLE_CLIENT_ID = "";
export const NAVER_CLIENT_ID = "";
export const NAVER_CALLBACK_URL = `${location.origin}${location.pathname.replace(/[^/]*$/, "")}intro.html`;
