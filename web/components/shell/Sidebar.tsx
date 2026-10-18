"use client";

// Barra lateral (DESIGN.md › sidebar, EXPERIENCE › Information Architecture): as 4 áreas e o botão
// Importar fixo. Item ativo = área da rota (inclusive nas URLs v1). Abaixo de 1024px empilha
// acima do conteúdo.
import { LayoutDashboardIcon, type LucideIcon, SettingsIcon, TrendingUpIcon, WalletIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { ImportHub } from "@/components/ingest/ImportHub";
import { AREAS, type AreaKey, areaOf, tabHref } from "@/lib/nav";
import { cn } from "@/lib/utils";

const ICONS: Record<AreaKey, LucideIcon> = {
  "visao-geral": LayoutDashboardIcon,
  caixa: WalletIcon,
  investimentos: TrendingUpIcon,
  ajustes: SettingsIcon,
};

export function Sidebar() {
  const pathname = usePathname();
  const search = useSearchParams();
  const active = areaOf(pathname);
  return (
    <aside className="flex shrink-0 flex-col gap-4 border-b border-sidebar-border bg-sidebar p-4 text-sidebar-foreground lg:sticky lg:top-0 lg:h-screen lg:w-sidebar lg:border-r lg:border-b-0">
      <Link href="/visao-geral/painel" className="flex items-center gap-2 px-2 font-mono text-base font-semibold">
        <span aria-hidden className="size-3 rounded-xs bg-positive" />
        goodies
      </Link>
      <ImportHub />
      <nav aria-label="Áreas" className="flex flex-wrap gap-1 lg:flex-col">
        {AREAS.map((area) => {
          const Icon = ICONS[area.key];
          const isActive = active === area.key;
          return (
            <Link
              key={area.key}
              href={tabHref(area.key, area.tabs[0].slug, search)}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "relative flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-sidebar-accent font-semibold text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent",
              )}
            >
              {isActive && (
                <span aria-hidden className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-positive" />
              )}
              <Icon className="size-4" aria-hidden />
              {area.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
