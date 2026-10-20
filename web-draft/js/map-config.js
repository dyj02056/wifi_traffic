// 지도 설정. KAKAO_JS_KEY가 있으면 카카오맵, 비어 있으면 Leaflet(오픈스트리트맵)으로 그린다.
//
// 카카오 JavaScript 키 받는 법: https://developers.kakao.com → 내 애플리케이션 → 애플리케이션 추가
//   → 앱 키의 "JavaScript 키" 복사 → [플랫폼 > Web]에 사이트 도메인 http://localhost:5501 (배포 주소도) 등록
//   → 카카오맵 사용 설정이 꺼져 있으면 켠다.
// JavaScript 키는 브라우저에 노출되는 값이라 여기에 넣어도 된다(도메인 등록으로 보호). REST·Admin 키는 넣지 않는다.
export const KAKAO_JS_KEY = "";
