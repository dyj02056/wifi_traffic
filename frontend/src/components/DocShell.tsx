"use client";
// 문서형 화면 공통 틀: 상단 내비 + 샘플 데이터 배지, 로그인(비회원 포함) 안 했으면 인트로로
//
// [이 파일이 하는 일]
//   /rules, /sensitivity, /context, /about처럼 글 위주 화면이 함께 쓰는 '겉틀'입니다.
//   - 맨 위 메뉴(TopNav)를 그리고, 가짜 데이터·백업 데이터를 쓰는 중이면 배지로 알린다
//   - 로그인도 비회원 선택도 안 한 상태(session === null)면 첫 화면("/")으로 돌려보낸다
//   - children: 이 틀 안에 들어갈 각 화면의 본문
// SourceNote는 "출처: ○○ · 게재 날짜 · 확인 날짜" 한 줄을 그리는 작은 부품입니다.
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useSession } from "@/lib/auth";
import { useDataSource, useMeta } from "@/lib/queries";
import { TopNav } from "./TopNav";

export function DocShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const session = useSession();
  const meta = useMeta();
  const source = useDataSource();
  // useEffect: 화면을 그린 뒤 실행할 일. session이 바뀔 때마다 다시 확인한다
  useEffect(() => {
    if (session === null) router.replace("/");
  }, [session, router]);
  return (
    <div className="page">
      <TopNav badges={<>
        {meta.data?.is_mock && <span className="badge mock">샘플 데이터</span>}
        {source === "static" && <span className="badge static">정적 백업 데이터</span>}
      </>} />
      <main className="doc">{children}</main>
    </div>
  );
}

export function SourceNote({ name, url, retrieved, published }: {
  name: string; url: string; retrieved?: string | null; published?: string | null;
}) {
  return (
    <p className="sources">
      출처: {url.startsWith("http") ? <a href={url} target="_blank" rel="noopener noreferrer">{name}</a> : name}
      {published && ` · 게재 ${published}`}{retrieved && ` · 확인 ${retrieved}`}
    </p>
  );
}
