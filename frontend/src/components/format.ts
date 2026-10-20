export const fmt = (n: number | null | undefined) =>
  n == null ? "–" : Number(n).toFixed(2).replace(/\.?0+$/, "");

export const EVIDENCE_LABELS: Record<string, string> = {
  ssid: "SSID", facility_type: "설치시설구분", place_detail: "설치장소상세", install_ym: "설치연월",
  provider: "서비스제공사", manager: "관리기관", manager_tel: "관리기관 전화", data_date: "데이터기준일자",
  address: "주소", open_ap_within_radius: "반경 내 개방형 AP",
};

export const FLAG_LABELS: Record<string, string> = {
  R1_ssid_missing: "SSID 정보 없음(가정 비율)", R1_unlabeled: "SSID 라벨 없음(가정 비율)",
  R1_unknown: "SSID 분류 불명(가정 비율)", R2_unmapped: "시설구분 미등록(가정 비율)",
  R4_missing: "설치연월 결측(가정 비율)", R4_year_only: "설치연도만 있음",
  R5_boundary: "시군구 경계 근처 — 밀집도 과소평가 가능", R7_invalid_tel: "전화번호 형식 불일치",
  R8_missing: "데이터기준일자 결측",
  COORD_suspect: "좌표 이상 의심 — 지역 지도 범위 계산에서 제외(점수에는 영향 없음)",
};
