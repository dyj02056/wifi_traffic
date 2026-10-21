"use client";
// 상단: 1줄 남색 바(배지 · 가운데 로고 · 로그인), 2줄 흰 메뉴 줄(아이콘 + 이름, 쿠팡 상단 메뉴처럼 가운데 정렬)

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { logout, PROVIDER_LABEL, useSession } from "@/lib/auth";

/* 메뉴 아이콘: 22px 컬러 SVG (외부 이미지 없이) */
const ICONS: Record<string, ReactNode> = {
  "/map": (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <ellipse cx="12" cy="20.5" rx="6" ry="1.8" fill="#9fd8b4" />
      <path d="M12 2.5a6.5 6.5 0 0 0-6.5 6.5c0 4.6 6.5 11 6.5 11s6.5-6.4 6.5-11A6.5 6.5 0 0 0 12 2.5z" fill="#2f6cf0" />
      <circle cx="12" cy="9" r="2.6" fill="#fff" />
    </svg>
  ),
  "/rules": (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4.5" y="3.5" width="15" height="18" rx="2.5" fill="#ff9f1c" />
      <rect x="8.5" y="2" width="7" height="4" rx="1.5" fill="#c46a00" />
      <path d="M8 12.5l2.6 2.6L16.2 9.5" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  "/sensitivity": (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="5" fill="#8b5cf6" />
      <path d="M7 8h10M7 12h10M7 16h10" stroke="#e4d9ff" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="10" cy="8" r="1.9" fill="#fff" /><circle cx="15" cy="12" r="1.9" fill="#fff" /><circle cx="9" cy="16" r="1.9" fill="#fff" />
    </svg>
  ),
  "/context": (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3.5" y="12" width="4.2" height="8.5" rx="1.4" fill="#f5c33b" />
      <rect x="9.9" y="7" width="4.2" height="13.5" rx="1.4" fill="#f06464" />
      <rect x="16.3" y="3.5" width="4.2" height="17" rx="1.4" fill="#2f6cf0" />
    </svg>
  ),
  "/about": (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <ellipse cx="12" cy="5.5" rx="7.5" ry="2.8" fill="#14b8a6" />
      <path d="M4.5 5.5v6c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-6c0 1.5-3.4 2.8-7.5 2.8S4.5 7 4.5 5.5z" fill="#0f9488" />
      <path d="M4.5 11.5v6c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-6c0 1.5-3.4 2.8-7.5 2.8s-7.5-1.3-7.5-2.8z" fill="#0b766d" />
    </svg>
  ),
};

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
    <header className="top-nav">
      <div className="nav-top">
        <div className="nav-left">{badges}</div>
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
      </div>
      <nav className="nav-menu" aria-label="주 메뉴">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} aria-current={path === l.href ? "page" : undefined}>
            <span className="nav-icon">{ICONS[l.href]}</span>{l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
