// [이 파일이 하는 일] 여러 화면에서 함께 쓰는 숫자 표시 방법과 이름표(영어 칸 이름 → 한국어) 모음

// 점수를 소수 둘째 자리까지 보여 주되 끝의 0은 뗀다. 예) 72.50 → "72.5", 60 → "60", 값 없음 → "–"
export const fmt = (n: number | null | undefined) =>
  n == null ? "–" : Number(n).toFixed(2).replace(/\.?0+$/, "");

// 지점 상세의 '근거' 칸 이름 → 화면에 보일 한국어 이름
export const EVIDENCE_LABELS: Record<string, string> = {
  ssid: "SSID", facility_type: "설치시설구분", place_detail: "설치장소상세", install_ym: "설치연월",
  provider: "서비스제공사", manager: "관리기관", manager_tel: "관리기관 전화", data_date: "데이터기준일자",
  address: "주소", open_ap_within_radius: "반경 내 개방형 AP",
};

// 데이터 문제 표식(flag) → 화면에 보일 설명 (flag는 백엔드 rules.py·density.py·geo.py에서 붙인다)
export const FLAG_LABELS: Record<string, string> = {
  R1_ssid_missing: "SSID 정보 없음(가정 비율)", R1_unlabeled: "SSID 라벨 없음(가정 비율)",
  R1_unknown: "SSID 분류 불명(가정 비율)", R2_unmapped: "시설구분 미등록(가정 비율)",
  R4_missing: "설치연월 결측(가정 비율)", R4_year_only: "설치연도만 있음",
  R5_boundary: "시군구 경계 근처 — 밀집도 과소평가 가능", R7_invalid_tel: "전화번호 형식 불일치",
  R8_missing: "데이터기준일자 결측",
  R1_free_only: "정부 공공와이파이 일반접속(Free) SSID만 기재 — 보안접속(Secure) 함께 송출 여부 확인 불가(가정)",
  COORD_suspect: "좌표 이상 의심 — 지역 지도 범위 계산에서 제외(점수에는 영향 없음)",
};
