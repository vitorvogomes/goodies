"use client";

// Hooks do Painel principal (Story 4.1) — queryKey [engine, recurso, periodo] (AD-17).
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { Fonte, Painel } from "@/types/overview";

export function usePainel(periodo: string) {
  return useQuery({
    queryKey: ["overview", "painel", periodo],
    queryFn: () => apiFetch<Painel>(`/api/v1/overview/painel?periodo=${periodo}`),
  });
}

export function useOverviewSources() {
  return useQuery({
    queryKey: ["overview", "fontes"],
    queryFn: () => apiFetch<Fonte[]>("/api/v1/overview/fontes"),
  });
}
