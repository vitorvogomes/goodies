// Hook da reconciliação de trânsito (Pilar 2). Key sob ["portfolio"] -> invalidada
// junto com posições/XIRR quando importa B3 ou roda o catch-up.
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { Transit } from "@/types/portfolio";

export function useTransit() {
  return useQuery({
    queryKey: ["portfolio", "transit"],
    queryFn: () => apiFetch<Transit>("/api/v1/portfolio/transit"),
  });
}
