"use client";

// Hooks React Query do Market Engine (m3) — preços com staleness.
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { PricesResponse } from "@/types/market";

export function usePrices() {
  return useQuery({
    queryKey: ["market", "prices"],
    queryFn: () => apiFetch<PricesResponse>("/api/v1/market/prices"),
  });
}
