"use client";

// Navegação inferior no celular (v2.2 — F0): abaixo de 1024px as 4 áreas ficam numa barra fixa
// embaixo, ao alcance do polegar, no lugar da barra lateral. Respeita a área segura do iPhone.
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { AREA_ICONS } from "@/components/shell/Sidebar";
import { AREAS, areaOf, tabHref } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function BottomNav() {
  const pathname = usePathname();
  const search = useSearchParams();
  const active = areaOf(pathname);
  return (
    <nav
      aria-label="Áreas"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-sidebar-border bg-sidebar pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <ul className="grid grid-cols-4">
        {AREAS.map((area) => {
          const Icon = AREA_ICONS[area.key];
          const isActive = active === area.key;
          return (
            <li key={area.key}>
              <Link
                href={tabHref(area.key, area.tabs[0].slug, search)}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "flex min-h-14 flex-col items-center justify-center gap-1 px-1 type-caption",
                  isActive ? "font-semibold text-foreground" : "text-muted-foreground",
                )}
              >
                <Icon aria-hidden className={cn("size-5", isActive && "text-positive")} />
                {area.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
