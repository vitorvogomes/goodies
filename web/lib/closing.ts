"use client";

// Hooks do fechamento de mês (Stories 5.3–5.5) — queryKey [engine, recurso, periodo] (AD-17).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
import type { Checklist, ChecklistItem, MonthState, ReopenPreview } from "@/types/closing";

export function useMonthStates(de?: string, ate?: string) {
  const qs = new URLSearchParams();
  if (de) qs.set("de", de);
  if (ate) qs.set("ate", ate);
  return useQuery({
    queryKey: ["closing", "months", de ?? "", ate ?? ""],
    queryFn: () => apiFetch<MonthState[]>(`/api/v1/closing/months${qs.size ? `?${qs}` : ""}`),
  });
}

export function useChecklist(periodo: string | null) {
  return useQuery({
    queryKey: ["closing", "checklist", periodo],
    queryFn: () => apiFetch<Checklist>(`/api/v1/closing/months/${periodo}/checklist`),
    enabled: periodo !== null,
  });
}

export function useCloseMonth() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ periodo, confirmar }: { periodo: string; confirmar: string[] }) =>
      apiFetch<{ version: number; confirmations: ChecklistItem[] }>(
        `/api/v1/closing/months/${periodo}/close`,
        { method: "POST", body: JSON.stringify({ confirmar }) },
      ),
    onSuccess: () => invalidateAfter(queryClient, "closing"),
  });
}

export function useReopenPreview(periodo: string | null) {
  return useQuery({
    queryKey: ["closing", "reopen-preview", periodo],
    queryFn: () => apiFetch<ReopenPreview>(`/api/v1/closing/months/${periodo}/reopen/preview`),
    enabled: periodo !== null,
    retry: false, // 409 = o mês já não está fechado
  });
}

export function useReopenMonth() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (periodo: string) =>
      apiFetch<{ version: number }>(`/api/v1/closing/months/${periodo}/reopen`, { method: "POST" }),
    onSuccess: () => {
      // a prévia é do mês fechado: refazê-la com o mês aberto daria 409
      queryClient.removeQueries({ queryKey: ["closing", "reopen-preview"] });
      return invalidateAfter(queryClient, "closing");
    },
  });
}
