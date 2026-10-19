"use client";

// Barra lateral (DESIGN.md › sidebar, EXPERIENCE › Information Architecture): as 4 áreas e o botão
// Importar fixo. Item ativo = área da rota. Abaixo de 1024px empilha acima do conteúdo. A partir de
// 1024px recolhe para uma faixa de ícones (mais espaço para as tabelas) — a escolha fica lembrada
// no navegador.
import {
  LayoutDashboardIcon,
  type LucideIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  SettingsIcon,
  TrendingUpIcon,
  WalletIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";

import { ImportHub } from "@/components/ingest/ImportHub";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { AREAS, type AreaKey, areaOf, tabHref } from "@/lib/nav";
import { cn } from "@/lib/utils";

const ICONS: Record<AreaKey, LucideIcon> = {
  "visao-geral": LayoutDashboardIcon,
  caixa: WalletIcon,
  investimentos: TrendingUpIcon,
  ajustes: SettingsIcon,
};
const STORAGE_KEY = "goodies:sidebar:collapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function Sidebar() {
  const pathname = usePathname();
  const search = useSearchParams();
  const active = areaOf(pathname);
  // O shell só renderiza no cliente (depois do gate de sessão): ler o navegador aqui não diverge.
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const toggle = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem(STORAGE_KEY, c ? "0" : "1");
      } catch {
        /* preferência só local */
      }
      return !c;
    });
  };
  const ToggleIcon = collapsed ? PanelLeftOpenIcon : PanelLeftCloseIcon;
  return (
    <aside
      data-collapsed={collapsed || undefined}
      className={cn(
        "flex shrink-0 flex-col gap-4 border-b border-sidebar-border bg-sidebar p-4 text-sidebar-foreground transition-[width] lg:sticky lg:top-0 lg:h-screen lg:border-r lg:border-b-0",
        collapsed ? "lg:w-16 lg:items-center lg:px-2" : "lg:w-sidebar",
      )}
    >
      <div className={cn("flex items-center justify-between gap-2", collapsed && "lg:flex-col")}>
        <Link
          href="/visao-geral/painel"
          aria-label="goodies — Painel"
          className="flex items-center gap-2 px-2 font-mono text-base font-semibold"
        >
          <span aria-hidden className="size-3 rounded-xs bg-positive" />
          <span className={cn(collapsed && "lg:sr-only")}>goodies</span>
        </Link>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={toggle}
              aria-pressed={collapsed}
              aria-label={collapsed ? "Expandir a barra lateral" : "Recolher a barra lateral"}
              className="hidden size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground lg:flex"
            >
              <ToggleIcon className="size-4" aria-hidden />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">{collapsed ? "Expandir" : "Recolher"}</TooltipContent>
        </Tooltip>
      </div>
      <ImportHub compact={collapsed} />
      <nav aria-label="Áreas" className="flex flex-wrap gap-1 lg:flex-col">
        {AREAS.map((area) => {
          const Icon = ICONS[area.key];
          const isActive = active === area.key;
          const link = (
            <Link
              key={area.key}
              href={tabHref(area.key, area.tabs[0].slug, search)}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "relative flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                collapsed && "lg:justify-center lg:px-0",
                isActive
                  ? "bg-sidebar-accent font-semibold text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent",
              )}
            >
              {isActive && (
                <span aria-hidden className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-positive" />
              )}
              <Icon className="size-4 shrink-0" aria-hidden />
              <span className={cn(collapsed && "lg:sr-only")}>{area.label}</span>
            </Link>
          );
          return collapsed ? (
            <Tooltip key={area.key}>
              <TooltipTrigger asChild>{link}</TooltipTrigger>
              <TooltipContent side="right">{area.label}</TooltipContent>
            </Tooltip>
          ) : (
            link
          );
        })}
      </nav>
    </aside>
  );
}
