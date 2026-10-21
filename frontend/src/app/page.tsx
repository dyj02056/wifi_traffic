// 인트로·로그인 (plan.md §9.1 랜딩 + docs/requests.md #19)
//
// [이 파일이 하는 일]
//   사이트 첫 화면("/")입니다. 로고와 소개 문구를 보여 주고, 아래에 로그인 상자(LoginCard)를 놓습니다.
//   로그인하거나 '비회원으로 이용하기'를 누르면 지도 화면(/map)으로 이동합니다.
import { LoginCard } from "@/components/LoginCard";

export default function IntroPage() {
  return (
    <div className="intro-page">
      <main className="intro-main">
        <section className="hero">
          <div className="hero-mark">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="wifi-bg" src="/img/wifi.png" alt="" aria-hidden="true" />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="logo" src="/img/logo-cutout.png" alt="Wifi Traffic" />
          </div>
          <p className="tagline" lang="en">Scan Public Wi-Fi Risks by Color Before Connecting</p>
        </section>
        <LoginCard />
      </main>
    </div>
  );
}
