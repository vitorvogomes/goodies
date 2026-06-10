"use client";

// Hooks React Query do Portfolio (m2) — wrappers sobre apiFetch.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type {
  Allocation,
  AssetOperation,
  CryptoSleeve,
  Income,
  OperationFilters,
  Position,
  Rebalancing,
  XIRR,
} from "@/types/portfolio";

export function usePositions() {
  return useQuery({
    queryKey: ["portfolio", "positions"],
    queryFn: () => apiFetch<Position[]>("/api/v1/portfolio/positions"),
  });
}

export function useAllocation() {
  return useQuery({
    queryKey: ["portfolio", "allocation"],
    queryFn: () => apiFetch<Allocation>("/api/v1/portfolio/allocation"),
  });
}

export function useXIRR() {
  return useQuery({
    queryKey: ["portfolio", "xirr"],
    queryFn: () => apiFetch<XIRR>("/api/v1/portfolio/xirr"),
  });
}

export function useCryptoSleeve() {
  return useQuery({
    queryKey: ["portfolio", "crypto-sleeve"],
    queryFn: () => apiFetch<CryptoSleeve>("/api/v1/portfolio/crypto-sleeve"),
  });
}

export function useIncome() {
  return useQuery({
    queryKey: ["portfolio", "income"],
    queryFn: () => apiFetch<Income>("/api/v1/portfolio/income"),
  });
}

export function useRebalancing(amount: number) {
  return useQuery({
    queryKey: ["portfolio", "rebalancing", amount],
    queryFn: () =>
      apiFetch<Rebalancing>(`/api/v1/portfolio/rebalancing?amount=${amount}`),
    enabled: amount >= 0,
  });
}

function buildOpsQuery(filters: OperationFilters): string {
  const params = new URLSearchParams();
  if (filters.asset_symbol) params.set("asset_symbol", filters.asset_symbol);
  if (filters.tipo) params.set("tipo", filters.tipo);
  if (filters.data_from) params.set("data_from", filters.data_from);
  if (filters.data_to) params.set("data_to", filters.data_to);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useAssetOperations(filters: OperationFilters) {
  return useQuery({
    queryKey: ["portfolio", "operations", filters],
    queryFn: () =>
      apiFetch<AssetOperation[]>(
        `/api/v1/asset-operations${buildOpsQuery(filters)}`,
      ),
  });
}

export function useSetManualPrice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, price }: { symbol: string; price: number }) =>
      apiFetch<unknown>(`/api/v1/market/prices/${symbol}`, {
        method: "POST",
        body: JSON.stringify({ price_brl: price }),
      }),
    onSuccess: () => {
      // o preço alimenta tanto as posições quanto a tela de preços (/market)
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["market"] });
    },
  });
}

// Volta o preço ao automático (limpa is_manual): o worker volta a cotar. Usado quando o
// usuário digitou o valor líquido de um Tesouro/caixinha e quer deixar o worker assumir.
export function useRevertPrice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) =>
      apiFetch<unknown>(`/api/v1/market/prices/${symbol}/manual`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["market"] });
    },
  });
}
