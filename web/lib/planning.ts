"use client";

// Orçamento do mês (Stories 6.5–6.7): leitura por `closing`, escrita do plano por `planning`.
// Objetivos (Story 8.1): `planning`.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
import type {
  AporteSummary,
  Distribution,
  Goal,
  GoalIn,
  GoalsOut,
  MonthBudget,
  TargetsIn,
  TargetsOut,
  TargetsPreview,
} from "@/types/planning";

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

// ---- Metas de alocação (Story 8.2) ----

export function useTargets() {
  return useQuery({
    queryKey: ["planning", "targets"],
    queryFn: () => apiFetch<TargetsOut>("/api/v1/planning/targets"),
  });
}

// A soma de cada nível é conferida pela API (o navegador não soma).
export function useTargetsPreview(body: TargetsIn | null) {
  return useQuery({
    queryKey: ["planning", "targets-preview", body],
    queryFn: () =>
      apiFetch<TargetsPreview>("/api/v1/planning/targets/preview", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    enabled: body !== null,
  });
}

export function useSaveTargets() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TargetsIn) =>
      apiFetch<TargetsOut>("/api/v1/planning/targets", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => invalidateAfter(queryClient, "planning"),
  });
}

// ---- Aporte planejado (Story 8.4) ----

export function useSetAporte() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ periodo, valor }: { periodo: string; valor: string | null }) =>
      apiFetch<{ aporte_planejado: number | null }>(`/api/v1/planning/months/${periodo}/aporte`, {
        method: "PUT",
        body: JSON.stringify({ valor }),
      }),
    onSuccess: () => invalidateAfter(queryClient, "planning"),
  });
}

// ---- Distribuição do aporte (Story 8.5) ----

export function useDistribution(periodo: string, enabled: boolean) {
  return useQuery({
    queryKey: ["planning", "distribution", periodo],
    queryFn: () =>
      apiFetch<Distribution>("/api/v1/planning/distribution/preview", {
        method: "POST",
        body: JSON.stringify({ mes: periodo }),
      }),
    enabled,
  });
}

// ---- Travas da distribuição (Story 8.6) ----

// Grava (valor) ou tira (null) a trava e devolve a prévia nova (o resto redistribuído pela API).
export function useSetLock(periodo: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, valor }: { key: string; valor: string | null }) => {
      const url = `/api/v1/planning/months/${periodo}/travas/${encodeURIComponent(key)}`;
      await apiFetch<unknown>(url, valor === null ? { method: "DELETE" } : { method: "PUT", body: JSON.stringify({ valor }) });
      return apiFetch<Distribution>("/api/v1/planning/distribution/preview", {
        method: "POST",
        body: JSON.stringify({ mes: periodo }),
      });
    },
    onSuccess: (next) => queryClient.setQueryData(["planning", "distribution", periodo], next),
    // a trava pode ter sido gravada mesmo com a prévia falhando, e travas seguidas podem responder
    // fora de ordem: no fim, sempre a versão do servidor
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["planning", "distribution", periodo] }),
        queryClient.invalidateQueries({ queryKey: ["planning", "aporte-resumo", periodo] }),
      ]),
  });
}

// ---- Resumo do aporte no Painel (Story 8.8) ----

export function useAporteSummary(periodo: string) {
  return useQuery({
    queryKey: ["planning", "aporte-resumo", periodo],
    queryFn: () => apiFetch<AporteSummary>(`/api/v1/planning/months/${periodo}/aporte/resumo`),
  });
}
