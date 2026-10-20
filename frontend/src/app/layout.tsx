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
