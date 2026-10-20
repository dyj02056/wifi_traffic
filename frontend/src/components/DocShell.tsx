"use client";
// 문서형 화면 공통 틀: 상단 내비 + 샘플 데이터 배지, 로그인(비회원 포함) 안 했으면 인트로로
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
