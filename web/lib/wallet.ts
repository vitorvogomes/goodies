"use client";

// Hooks React Query do Wallet Engine (m4) — posições escaneadas/manuais,
// reconciliação e DeFi. Mutations invalidam ["wallets"], ["defi"] e ["portfolio"]: o saldo
// cripto entra no sleeve (Posições/Alocação/XIRR/Trânsito) e na reconciliação.
import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type {
  DefiPosition,
  DefiPositionInput,
  ManualItem,
  ManualPositionInput,
  Reconciliation,
  WalletPosition,
} from "@/types/wallet";

// Tudo que depende do saldo cripto (wallet/DeFi) — ver comentário do topo.
function invalidateCrypto(qc: QueryClient) {
  for (const key of ["wallets", "defi", "portfolio", "closing", "overview", "alerts"]) {
    qc.invalidateQueries({ queryKey: [key] });
  }
}

export function useWalletPositions() {
  return useQuery({
    queryKey: ["wallets", "positions"],
    queryFn: () => apiFetch<WalletPosition[]>("/api/v1/wallets/positions"),
  });
}

export function useReconciliation() {
  return useQuery({
    queryKey: ["wallets", "reconciliation"],
    queryFn: () => apiFetch<Reconciliation[]>("/api/v1/wallets/reconciliation"),
  });
}

export function useDefiPositions() {
  return useQuery({
    queryKey: ["defi", "positions"],
    queryFn: () => apiFetch<DefiPosition[]>("/api/v1/defi/positions"),
  });
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
export function useManualPositions() {
  return useQuery({
    queryKey: ["wallets", "manual"],
    queryFn: () => apiFetch<ManualItem[]>("/api/v1/wallets/manual"),
  });
}
