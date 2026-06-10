// Hooks de frescor / catch-up (Pilar 0). useFreshness lê o estado por job;
// useRefreshAll dispara o "Atualizar tudo" (force) ou o catch-up dos vencidos (false).
import {
  useIsMutating,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { JobStatus } from "@/types/jobs";

export interface RefreshResult {
  status: string; // "ran" | "already_running"
  jobs: Record<string, string>;
}

// mutationKey compartilhada entre o AppShell (catch-up) e a página /refresh: assim o
// botão sabe que já há um refresh rodando e não dispara um 2º (bloqueio de duplo clique).
export const REFRESH_MUTATION_KEY = ["jobs", "refresh"] as const;

export function useFreshness(pollWhileRunning = false) {
  return useQuery({
    queryKey: ["jobs", "status"],
    queryFn: () => apiFetch<JobStatus[]>("/api/v1/jobs/status"),
    // enquanto um refresh roda, re-busca o frescor p/ a UI acompanhar o progresso
    refetchInterval: pollWhileRunning ? 2000 : false,
  });
}

/** Quantos refreshes estão em andamento agora (AppShell + página somados). */
export function useRefreshRunning(): boolean {
  return useIsMutating({ mutationKey: REFRESH_MUTATION_KEY }) > 0;
}

export function useRefreshAll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: REFRESH_MUTATION_KEY,
    mutationFn: (force: boolean) =>
      apiFetch<RefreshResult>(`/api/v1/jobs/refresh?force=${force}`, { method: "POST" }),
    onSuccess: () => {
      // o refresh roda wallet_scan + price_* + benchmark: invalida tudo que muda,
      // inclusive ["wallets"] (Carteiras/Reconciliação ficavam com cache velho).
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["market"] });
      queryClient.invalidateQueries({ queryKey: ["wallets"] });
    },
  });
}
