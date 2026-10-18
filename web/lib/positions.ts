"use client";

// Investimentos › Posições (Story 7.1) — queryKey [engine, recurso, periodo, leitura] (AD-17).
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { invalidateAfter } from "@/lib/invalidate";
import type { Leitura } from "@/lib/period";
import type {
  BrokerCard,
  Debenture,
  DebentureIn,
  PositionsReport,
  Reconciliation,
} from "@/types/positions";

export function usePositions(periodo: string, leitura: Leitura) {
  return useQuery({
    queryKey: ["closing", "positions", periodo, leitura],
    queryFn: () =>
      apiFetch<PositionsReport>(`/api/v1/closing/positions?periodo=${periodo}&leitura=${leitura}`),
  });
}

// ---- Ajustes › Debêntures (Story 7.6) ----

export function useDebentures() {
  return useQuery({
    queryKey: ["portfolio", "debentures"],
    queryFn: () => apiFetch<Debenture[]>("/api/v1/portfolio/debentures"),
  });
}

export function useSaveDebenture() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string | null; body: DebentureIn }) =>
      apiFetch<Debenture>(`/api/v1/portfolio/debentures${id ? `/${id}` : ""}`, {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateAfter(queryClient, "portfolio"),
  });
}

// ---- Caixa em corretora (Story 7.7) ----

export function useBrokers() {
  return useQuery({
    queryKey: ["portfolio", "brokers"],
    queryFn: () => apiFetch<BrokerCard[]>("/api/v1/portfolio/brokers"),
  });
}

export function useBrokerCheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { rail: string; as_of: string; balance: string }) =>
      apiFetch<BrokerCard[]>("/api/v1/portfolio/brokers/checks", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateAfter(queryClient, "portfolio"),
  });
}

// ---- Conciliação com o consolidado B3 e as carteiras (Story 7.9) ----

export function useReconciliation() {
  return useQuery({
    queryKey: ["portfolio", "reconciliation"],
    queryFn: () => apiFetch<Reconciliation>("/api/v1/portfolio/reconciliation"),
  });
}

// "Tudo bate com o consolidado B3 de {data} e com as carteiras de {data}." — só quando tudo bate.
export function reconciliationSummary(r: Reconciliation): string | null {
  if (!r.all_ok || !r.b3.ref_date) return null;
  const b3 = `com o consolidado B3 de ${formatDate(r.b3.ref_date)}`;
  const when = r.wallets.scanned_at ?? r.wallets.attempt_at;
  if (!r.wallets.rows.length || !when) return `Tudo bate ${b3}.`;
  const day = new Date(when).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
  return `Tudo bate ${b3} e com as carteiras de ${day}.`;
}

// ---- Operações (Story 10.6 — substituto da tela v1 /portfolio/history) ----

export interface OperationRow {
  id: string;
  data_operacao: string;
  asset_symbol: string;
  asset_category: string;
  tipo: string;
  quantidade: string;
  valor_unitario: string; // decimal em texto, sem arredondar
  total: number;
}

export function useOperations(filters: { ativo: string; tipo: string; de: string; ate: string }) {
  const q = new URLSearchParams();
  if (filters.ativo) q.set("asset_symbol", filters.ativo);
  if (filters.tipo) q.set("tipo", filters.tipo);
  if (filters.de) q.set("data_from", filters.de);
  if (filters.ate) q.set("data_to", filters.ate);
  return useQuery({
    queryKey: ["portfolio", "operations-v2", q.toString()],
    queryFn: () => apiFetch<OperationRow[]>(`/api/v1/portfolio/operations?${q}`),
    placeholderData: keepPreviousData, // filtro novo: a lista anterior fica até a nova chegar
  });
}
