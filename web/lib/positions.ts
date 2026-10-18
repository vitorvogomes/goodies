"use client";

// Investimentos › Posições (Story 7.1) — queryKey [engine, recurso, periodo, leitura] (AD-17).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
import type { Leitura } from "@/lib/period";
import type { Debenture, DebentureIn, PositionsReport } from "@/types/positions";

export function usePositions(periodo: string, leitura: Leitura) {
  return useQuery({
    queryKey: ["closing", "positions", periodo, leitura],
    queryFn: () =>
      apiFetch<PositionsReport>(`/api/v1/closing/positions?periodo=${periodo}&leitura=${leitura}`),
  });
}

// ---- Ajustes › Debêntures (Story 7.6) ----

export function useDebentures() {
  return useQuery({
    queryKey: ["portfolio", "debentures"],
    queryFn: () => apiFetch<Debenture[]>("/api/v1/portfolio/debentures"),
  });
}

export function useSaveDebenture() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string | null; body: DebentureIn }) =>
      apiFetch<Debenture>(`/api/v1/portfolio/debentures${id ? `/${id}` : ""}`, {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateAfter(queryClient, "portfolio"),
  });
}
