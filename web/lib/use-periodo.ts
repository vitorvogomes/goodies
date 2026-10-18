"use client";

// Período global da URL (Story 1.8): lê `?periodo=`, normaliza (mês atual BRT por padrão; antes de
// jul/2024 → jul/2024) e troca mantendo a rota e os demais parâmetros.
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect } from "react";

import { normalizePeriodo } from "@/lib/period";

export function usePeriodo(): { periodo: string; setPeriodo: (month: string) => void } {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const raw = search.get("periodo");
  const periodo = normalizePeriodo(raw);

  const hrefWith = useCallback(
    (month: string) => {
      const q = new URLSearchParams(search.toString());
      q.set("periodo", month);
      return `${pathname}?${q.toString()}`;
    },
    [pathname, search],
  );

  // URL com período inválido ou fora da faixa é corrigida no lugar (sem nova entrada no histórico).
  useEffect(() => {
    if (raw !== null && raw !== periodo) router.replace(hrefWith(periodo));
  }, [raw, periodo, router, hrefWith]);

  const setPeriodo = useCallback((month: string) => router.push(hrefWith(month)), [router, hrefWith]);
  return { periodo, setPeriodo };
}
