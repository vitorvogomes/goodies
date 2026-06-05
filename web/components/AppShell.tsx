"use client";

// Shell da área autenticada (m1): sidebar + gate de acesso.
// O access token vive em memória (ADR-006); num reload duro ele se perde, então
// tentamos renová-lo pelo cookie httpOnly de refresh antes de cair no /login.
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { cn } from "@/components/ui";
import { refreshAccessToken } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/analise-ledger", label: "Análise" },
  { href: "/ledger", label: "Transações" },
  { href: "/ledger/new", label: "Nova transação" },
  { href: "/ledger/import", label: "Importar extrato" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/portfolio/positions", label: "Posições" },
  { href: "/portfolio/allocation", label: "Alocação" },
  { href: "/portfolio/rebalancing", label: "Rebalanceamento" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

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
      else router.replace("/login");
    })();
    return () => {
      active = false;
    };
  }, [router]);

  if (!ready) {
    return (
      <div className="flex flex-1 items-center justify-center text-foreground/50">Carregando…</div>
    );
  }

  return (
    <div className="flex flex-1">
      <aside className="w-56 shrink-0 border-r border-border bg-muted/30 p-4">
        <div className="mb-6 px-2 font-mono text-lg font-semibold text-foreground">Goodies</div>
        <nav className="space-y-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "block rounded-lg px-3 py-2 text-sm transition",
                pathname === item.href
                  ? "bg-accent/15 text-foreground"
                  : "text-foreground/60 hover:bg-muted hover:text-foreground",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-6 md:p-8">{children}</main>
    </div>
  );
}
