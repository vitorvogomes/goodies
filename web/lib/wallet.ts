"use client";

// Hooks React Query do Wallet Engine (m4) — posições manuais e DeFi. Mutations invalidam ["wallets"], ["defi"] e ["portfolio"]: o saldo
// cripto entra no sleeve (Posições/Alocação/XIRR/Trânsito) e na reconciliação.
import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type {
  DefiBalanceInput,
  DefiPositionInput,
  ManualItem,
  ManualPositionInput,
} from "@/types/wallet";

// Tudo que depende do saldo cripto (wallet/DeFi) — ver comentário do topo.
function invalidateCrypto(qc: QueryClient) {
  for (const key of ["wallets", "defi", "portfolio", "closing", "overview", "alerts"]) {
    qc.invalidateQueries({ queryKey: [key] });
  }
}

export function useCreateManualPosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ManualPositionInput) =>
      apiFetch<unknown>("/api/v1/wallets/positions/manual", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateCrypto(qc),
  });
}

export function useDeleteManualPosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ chain, asset_symbol }: { chain: string; asset_symbol: string }) =>
      apiFetch<unknown>(
        `/api/v1/wallets/positions/manual/${encodeURIComponent(chain)}/${encodeURIComponent(asset_symbol)}`,
        { method: "DELETE" },
      ),
    onSuccess: () => invalidateCrypto(qc),
  });
}

export function useCreateDefi() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DefiPositionInput) =>
      apiFetch<unknown>("/api/v1/defi/positions", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateCrypto(qc),
  });
}

export function useUpdateDefi() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Partial<DefiPositionInput>) =>
      apiFetch<unknown>(`/api/v1/defi/positions/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateCrypto(qc),
  });
}

export function useDeleteDefi() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<unknown>(`/api/v1/defi/positions/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateCrypto(qc),
  });
}

// Ajustes › Posições manuais (Story 7.8): carteira manual + DeFi numa lista só.
/** v2.2: o saldo em US$ que o protocolo mostra (+ APY opcional) — o preço do token sai dele. */
export function useSetDefiBalance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & DefiBalanceInput) =>
      apiFetch<unknown>(`/api/v1/defi/positions/${id}/balance`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateCrypto(qc),
  });
}

export function useManualPositions() {
  return useQuery({
    queryKey: ["wallets", "manual"],
    queryFn: () => apiFetch<ManualItem[]>("/api/v1/wallets/manual"),
  });
}
