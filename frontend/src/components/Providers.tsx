"use client";
// [이 파일이 하는 일]
//   사이트 전체를 감싸서, 모든 화면이 같은 데이터 보관함(QueryClient)을 함께 쓰게 해 줍니다.
//   app/layout.tsx가 이 부품으로 모든 페이지를 감쌉니다. 그래서 queries.ts의 훅들이 어느 화면에서든 동작합니다.

import { useEffect, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { onDataSourceChange } from "@/lib/api";

let browserQueryClient: QueryClient | undefined;

// 서버에서 화면을 미리 그릴 때는 요청마다 새 보관함을, 브라우저에서는 하나를 만들어 계속 쓴다
function getQueryClient() {
  if (typeof window === "undefined") return new QueryClient();
  browserQueryClient ??= new QueryClient();
  return browserQueryClient;
}

export function Providers({ children }: { children: ReactNode }) {
  const client = getQueryClient();
  // 백업(정적 번들)에서 API로 돌아오면 백업에서 받은 문서·실패한 요청을 API에서 다시 받는다
  useEffect(() => {
    const off = onDataSourceChange((s) => {
      if (s === "api") client.invalidateQueries();
    });
    return () => { off(); };
  }, [client]);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
