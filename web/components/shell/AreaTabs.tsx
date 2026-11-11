"use client";

// Abas da área (DESIGN.md › tabs): na URL; ←/→ trocam de aba (roving focus do Radix, ativação
// automática). Trocar de aba mantém o período.
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type AreaKey, getArea, tabHref } from "@/lib/nav";

export function AreaTabs({ area }: { area: AreaKey }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const def = getArea(area);
  const current = pathname.split("/")[2] ?? def.tabs[0].slug;
  return (
    <div className="space-y-3">
      <h1 className="type-page-title">{def.label}</h1>
      <Tabs value={current} onValueChange={(slug) => router.push(tabHref(area, slug, search))}>
        {/* No celular as abas rolam na horizontal (Ajustes tem 10), sem quebrar em várias linhas. */}
        <div className="-mx-page-gutter overflow-x-auto px-page-gutter [scrollbar-width:none] sm:mx-0 sm:overflow-visible sm:px-0">
          <TabsList
            variant="line"
            aria-label={`Abas de ${def.label}`}
            className="h-auto justify-start sm:flex-wrap"
          >
            {def.tabs.map((t) => (
              <TabsTrigger key={t.slug} value={t.slug} className="min-h-11 flex-none sm:min-h-0">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
      </Tabs>
    </div>
  );
}
