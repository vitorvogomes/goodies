"use client";

// Shell da área autenticada: Barra lateral das 4 áreas + Barra superior fixa (Story 1.7) + gate
// de acesso.
// O access token vive em memória (ADR-006); num reload duro ele se perde, então
// tentamos renová-lo pelo cookie httpOnly de refresh antes de cair no /login.
import { useRouter } from "next/navigation";
import { type ReactNode, Suspense, useEffect, useRef, useState } from "react";

import { PeriodSelector } from "@/components/shell/PeriodSelector";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";
import { refreshAccessToken } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { useRefreshAll } from "@/lib/jobs";
import { loginUrl } from "@/lib/next-url";

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const { mutate: refreshAll } = useRefreshAll();
  const caughtUp = useRef(false);

  useEffect(() => {
    // O access token vive só em memória (pós-mount). Se sumiu (reload duro),
    // tenta renovar pelo cookie httpOnly de refresh antes de redirecionar.
    let active = true;
    (async () => {
      if (getAccessToken()) {
        if (active) setReady(true);
        return;
      }
      const refreshed = await refreshAccessToken();
      if (!active) return;
      if (refreshed) setReady(true);
      else router.replace(loginUrl(window.location.pathname, window.location.search));
    })();
    return () => {
      active = false;
    };
  }, [router]);

  // Catch-up local: ao abrir o app (pós-auth), atualiza o que estiver vencido — uma
  // vez por carga, fail-soft (não bloqueia a UI). Só roda os jobs realmente vencidos.
  useEffect(() => {
    if (!ready || caughtUp.current) return;
    caughtUp.current = true;
    refreshAll(false);
  }, [ready, refreshAll]);

  if (!ready) {
    return (
      <div className="flex flex-1 items-center justify-center text-foreground/50">Carregando…</div>
    );
  }

  return (
    <div className="flex min-h-screen flex-1 flex-col lg:flex-row">
      <Suspense>
        <Sidebar />
      </Suspense>
      <div className="flex min-w-0 flex-1 flex-col">
        <Suspense fallback={<TopBar />}>
          <TopBar left={<PeriodSelector />} />
        </Suspense>
        <main className="mx-auto w-full max-w-content flex-1 px-page-gutter py-section-gap">
          {children}
        </main>
      </div>
    </div>
  );
}
