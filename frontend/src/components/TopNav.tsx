"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { logout, PROVIDER_LABEL, useSession } from "@/lib/auth";

const LINKS = [
  { href: "/map", label: "지도" },
  { href: "/rules", label: "채점 기준" },
  { href: "/sensitivity", label: "민감도" },
  { href: "/context", label: "배경 통계·사례" },
  { href: "/about", label: "데이터와 한계" },
];

export function TopNav({ badges }: { badges?: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const session = useSession();

  return (
    <nav className="top-nav">
      <div className="nav-left">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} aria-current={path === l.href ? "page" : undefined}>{l.label}</Link>
        ))}
        {badges}
      </div>
      <Link className="brand" href="/map">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/img/logo-cutout.png" alt="Wifi Traffic — 공공와이파이 안전 지도" />
      </Link>
      <div className="nav-right">
        {session && (
          <span className="user-box">
            {session.type === "member" ? (
              <span className="user-name">
                [{PROVIDER_LABEL[session.user.provider]}] {session.user.display_name} 님
                {session.user.sido && ` (${[session.user.sido, session.user.sigungu].filter(Boolean).join(" ")})`}
              </span>
            ) : (
              <span className="badge guest" title="비회원은 리뷰·평가·이벤트에 참여할 수 없습니다">비회원</span>
            )}
            <button type="button" onClick={() => { logout(); router.push("/"); }}>
              {session.type === "member" ? "로그아웃" : "로그인/회원가입"}
            </button>
          </span>
        )}
      </div>
    </nav>
  );
}
