"use client";

// Orçamento do mês (Stories 6.5–6.7): leitura por `closing`, escrita do plano por `planning`.
// Objetivos (Story 8.1): `planning`.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
import type { Goal, GoalIn, GoalsOut, MonthBudget } from "@/types/planning";

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

// ---- Objetivos (Story 8.1) ----

export function useGoals() {
  return useQuery({
    queryKey: ["planning", "goals"],
    queryFn: () => apiFetch<GoalsOut>("/api/v1/planning/goals"),
  });
}

export function useSaveGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string | null; body: GoalIn }) =>
      apiFetch<Goal>(`/api/v1/planning/goals${id ? `/${id}` : ""}`, {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateAfter(queryClient, "planning"),
  });
}

export function useDeleteGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/api/v1/planning/goals/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateAfter(queryClient, "planning"),
  });
}

export function useLinkGoalAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ goalId, assetId }: { goalId: string; assetId: string }) =>
      apiFetch<Goal>(`/api/v1/planning/goals/${goalId}/assets`, {
        method: "POST",
        body: JSON.stringify({ asset_id: assetId }),
      }),
    onSuccess: () => invalidateAfter(queryClient, "planning"),
  });
}

export function useDismissGoalSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assetId: string) =>
      apiFetch<void>(`/api/v1/planning/goal-suggestions/${assetId}/dismiss`, { method: "POST" }),
    onSuccess: () => invalidateAfter(queryClient, "planning"),
  });
}
