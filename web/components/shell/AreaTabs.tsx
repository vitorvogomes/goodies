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
        <TabsList variant="line" aria-label={`Abas de ${def.label}`} className="h-auto flex-wrap justify-start">
          {def.tabs.map((t) => (
            <TabsTrigger key={t.slug} value={t.slug} className="flex-none">
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  );
}
