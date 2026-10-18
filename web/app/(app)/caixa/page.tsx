import { redirect } from "next/navigation";

import { getArea, tabHref } from "@/lib/nav";

// A área abre na primeira aba, mantendo o período da URL.
export default async function AreaIndex({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const q = await searchParams;
  const periodo = typeof q.periodo === "string" ? q.periodo : null;
  const area = getArea("caixa");
  redirect(tabHref(area.key, area.tabs[0].slug, new URLSearchParams(periodo ? { periodo } : {})));
}
