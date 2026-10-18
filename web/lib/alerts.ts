"use client";

// Hooks da Central de avisos (Story 3.1) — queryKey [engine, recurso] (AD-17); toda mutação de outra
// engine já invalida "alerts" (lib/invalidate).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { AlertAction, AlertList } from "@/types/alerts";

export function useAlertCenter() {
  return useQuery({
    queryKey: ["alerts", "list"],
    queryFn: () => apiFetch<AlertList>("/api/v1/alerts"),
    refetchInterval: 5 * 60_000,
  });
}

export function useDismissAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { key: string; fingerprint: string }) =>
      apiFetch<void>("/api/v1/alerts/dismissals", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

/** Rota da ação com os parâmetros na query ("leva à tela filtrada"). */
export function actionHref(action: AlertAction): string {
  const query = new URLSearchParams(action.params).toString();
  return query ? `${action.route}?${query}` : action.route;
}
