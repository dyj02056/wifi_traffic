// 면책 배너: 모든 화면 상단 고정, 애니메이션 없음 (plan.md §9.2, scripts/check_disclaimer.py가 검사)
//
// [이 파일이 하는 일]
//   모든 화면 맨 위에 "점수는 위험요인 지표일 뿐"이라는 안내 문구 띠를 붙입니다.
//   app/layout.tsx가 이 부품을 쓰기 때문에 어느 페이지로 가도 항상 보입니다.
//   문구는 백엔드 config/rules.py의 DISCLAIMER와 글자 하나까지 같아야 합니다.
//   (컴포넌트: 화면의 한 조각을 그리는 함수. HTML처럼 생긴 JSX를 돌려준다)
export const DISCLAIMER = "이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.";

export function DisclaimerBar() {
  return (
    <div className="disclaimer-bar" role="note" data-disclaimer>
      ※ {DISCLAIMER}
    </div>
  );
}
