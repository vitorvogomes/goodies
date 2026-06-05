"use client";

// Providers globais — STORY-00-06.
// TanStack Query v5 (estado de servidor) + next-themes (dark-only no MVP, ADR-009).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";

import { ApiError } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  // Uma instância por ciclo de vida do app (evita recriar a cada render).
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // 401 já é tratado no apiFetch (refresh + retry) — não re-tentar aqui.
            retry: (failureCount, error) =>
              !(error instanceof ApiError && error.status === 401) &&
              failureCount < 2,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  );
}
