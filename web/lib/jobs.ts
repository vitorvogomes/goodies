// Hooks de frescor / catch-up (Pilar 0). useFreshness lê o estado por job;
// useRefreshAll dispara o "Atualizar tudo" (force) ou o catch-up dos vencidos (false).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { JobStatus } from "@/types/jobs";

interface RefreshResult {
  status: string;
  jobs: Record<string, string>;
}

export function useFreshness() {
  return useQuery({
    queryKey: ["jobs", "status"],
    queryFn: () => apiFetch<JobStatus[]>("/api/v1/jobs/status"),
  });
}

export function useRefreshAll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (force: boolean) =>
      apiFetch<RefreshResult>(`/api/v1/jobs/refresh?force=${force}`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["market"] });
    },
  });
}
