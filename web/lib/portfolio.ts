"use client";

// Hooks React Query do Portfolio (m2) — wrappers sobre apiFetch.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
// ---- Ajustes › Preços manuais (Story 10.2) ----

export interface ManualPrice {
  ticker: string;
  label: string;
  price_brl: string | null; // decimal em texto (preço unitário, até 8 casas)
  as_of: string | null;
  is_manual: boolean;
}

export function useManualPrices() {
  return useQuery({
    queryKey: ["portfolio", "manual-prices"],
    queryFn: () => apiFetch<ManualPrice[]>("/api/v1/portfolio/manual-prices"),
  });
}

// Grava valor + data (is_manual no market); ativo com fonte de mercado volta 409 com a mensagem.
export function useSaveManualPrice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ticker, price, asOf }: { ticker: string; price: string; asOf: string }) =>
      apiFetch<unknown>(`/api/v1/market/prices/${encodeURIComponent(ticker)}`, {
        method: "POST",
        body: JSON.stringify({ price_brl: price, as_of: asOf }),
      }),
    onSuccess: () => invalidateAfter(queryClient, "market"),
  });
}
