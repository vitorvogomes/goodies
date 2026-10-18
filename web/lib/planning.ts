"use client";

// Orçamento do mês (Stories 6.5–6.7): leitura por `closing`, escrita do plano por `planning`.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
import type { MonthBudget } from "@/types/planning";

export function useMonthBudget(periodo: string) {
  return useQuery({
    queryKey: ["closing", "budget", periodo],
    queryFn: () => apiFetch<MonthBudget>(`/api/v1/closing/months/${periodo}/budget`),
  });
}

export function useSetDividas() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ periodo, valor }: { periodo: string; valor: string | null }) =>
      apiFetch<{ dividas: number | null }>(`/api/v1/planning/months/${periodo}/dividas`, {
        method: "PUT",
        body: JSON.stringify({ valor }),
      }),
    onSuccess: () => invalidateAfter(queryClient, "planning"),
  });
}
