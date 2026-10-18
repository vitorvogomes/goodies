"use client";

// Investimentos › Posições (Story 7.1) — queryKey [engine, recurso, periodo, leitura] (AD-17).
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { Leitura } from "@/lib/period";
import type { PositionsReport } from "@/types/positions";

export function usePositions(periodo: string, leitura: Leitura) {
  return useQuery({
    queryKey: ["closing", "positions", periodo, leitura],
    queryFn: () =>
      apiFetch<PositionsReport>(`/api/v1/closing/positions?periodo=${periodo}&leitura=${leitura}`),
  });
}
