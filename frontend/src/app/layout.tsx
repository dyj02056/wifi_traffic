// [이 파일이 하는 일]
//   Next.js에서 layout.tsx는 모든 페이지를 감싸는 '공통 뼈대'입니다. 어느 주소로 가든 이 틀 안에 페이지가 들어갑니다.
//   - 맨 위에 면책 배너(DisclaimerBar)를 항상 붙인다 (scripts/check_disclaimer.py가 이 사용 여부를 검사)
//   - Providers로 감싸 모든 페이지가 같은 데이터 보관함을 쓰게 한다
//   - 전체 스타일(globals.css)을 불러온다
//   - metadata: 브라우저 탭 제목과 검색엔진용 설명, viewport: 휴대폰 화면 폭에 맞추는 설정
// (app/ 폴더 구조가 곧 사이트 주소: app/page.tsx = "/", app/map/page.tsx = "/map" …)
import type { Metadata, Viewport } from "next";
import { DisclaimerBar } from "@/components/DisclaimerBar";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Wifi Traffic — 공공와이파이 안전 지도",
  description: "접속하기 전에 공공와이파이 위험요인을 색으로 확인하세요. 이 점수는 실제 해킹 확률이 아니라 위험요인 지표입니다.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko">
      <body>
        <DisclaimerBar />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
