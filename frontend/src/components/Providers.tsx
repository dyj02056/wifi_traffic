"use client";

import { useEffect, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { onDataSourceChange } from "@/lib/api";

let browserQueryClient: QueryClient | undefined;

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
