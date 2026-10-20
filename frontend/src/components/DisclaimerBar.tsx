// 면책 배너: 모든 화면 상단 고정, 애니메이션 없음 (plan.md §9.2, scripts/check_disclaimer.py가 검사)
export const DISCLAIMER = "이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.";

export function DisclaimerBar() {
  return (
    <div className="disclaimer-bar" role="note" data-disclaimer>
      ※ {DISCLAIMER}
    </div>
  );
}
