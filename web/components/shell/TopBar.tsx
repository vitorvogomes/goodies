"use client";

// Barra superior (56px, fixa no scroll): Seletor de período à esquerda; Sino de avisos e Switch de
// tema à direita.
import type { ReactNode } from "react";

import { ThemeSwitch } from "@/components/shell/ThemeSwitch";

export function TopBar({ left, bell }: { left?: ReactNode; bell?: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 flex h-topbar items-center justify-between gap-2 border-b border-border bg-background px-page-gutter">
      <div className="flex items-center gap-2">{left}</div>
      <div className="flex items-center gap-2">
        {bell}
        <ThemeSwitch />
      </div>
    </header>
  );
}
