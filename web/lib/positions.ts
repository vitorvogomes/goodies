"use client";

// Investimentos › Posições (Story 7.1) — queryKey [engine, recurso, periodo, leitura] (AD-17).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
import type { Leitura } from "@/lib/period";
import type { BrokerCard, Debenture, DebentureIn, PositionsReport } from "@/types/positions";

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

// ---- Caixa em corretora (Story 7.7) ----

export function useBrokers() {
  return useQuery({
    queryKey: ["portfolio", "brokers"],
    queryFn: () => apiFetch<BrokerCard[]>("/api/v1/portfolio/brokers"),
  });
}

export function useBrokerCheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { rail: string; as_of: string; balance: string }) =>
      apiFetch<BrokerCard[]>("/api/v1/portfolio/brokers/checks", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateAfter(queryClient, "portfolio"),
  });
}
