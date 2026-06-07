"use client";

// Hooks React Query do Wallet Engine (m4) — posições escaneadas/manuais,
// reconciliação e DeFi. Mutations invalidam ["wallets"] / ["defi"].
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type {
  DefiPosition,
  DefiPositionInput,
  ManualPositionInput,
  Reconciliation,
  WalletPosition,
} from "@/types/wallet";

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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wallets"] }),
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wallets"] }),
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["defi"] }),
  });
}

export function useDeleteDefi() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<unknown>(`/api/v1/defi/positions/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["defi"] }),
  });
}
