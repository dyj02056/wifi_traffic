// 인트로·로그인 (plan.md §9.1 랜딩 + docs/requests.md #19)
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
