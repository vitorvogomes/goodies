"use client";

// Abas da área (DESIGN.md › tabs): na URL; ←/→ trocam de aba (roving focus do Radix, ativação
// automática). Trocar de aba mantém o período; as telas v1 ficam como links abaixo, nunca como aba.
import Link from "next/link";
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
      {def.v1.length > 0 && (
        <p className="type-caption text-muted-foreground">
          Telas da v1:{" "}
          {def.v1.map((l, i) => (
            <span key={l.href}>
              {i > 0 && " · "}
              <Link href={l.href} className="text-positive underline underline-offset-4 hover:no-underline">
                {l.label}
              </Link>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}
