// Invalidação cruzada (AD-17): toda mutação invalida a própria engine e as que leem dela.
import type { QueryClient } from "@tanstack/react-query";

const DEPENDENTS = ["planning", "portfolio", "closing", "alerts", "overview"] as const;

export function invalidateAfter(queryClient: QueryClient, ...engines: string[]): Promise<void[]> {
  return Promise.all(
    [...new Set([...engines, ...DEPENDENTS])].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
  );
}
