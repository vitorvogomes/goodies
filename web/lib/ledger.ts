"use client";

// Hooks React Query do Ledger (m1) — wrappers sobre apiFetch.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { API_BASE_URL, ApiError, apiFetch } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type {
  Account,
  Alert,
  CashflowProjection,
  Category,
  CategoryKind,
  ImportReport,
  MonthlySummary,
  Transaction,
  TransactionCreate,
  TransactionFilters,
  TransactionList,
} from "@/types/ledger";

export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiFetch<Account[]>("/api/v1/accounts"),
  });
}

export function useCategories(kind?: CategoryKind) {
  return useQuery({
    queryKey: ["categories", kind ?? "all"],
    queryFn: () =>
      apiFetch<Category[]>(`/api/v1/categories${kind ? `?kind=${kind}` : ""}`),
  });
}

function buildQuery(filters: TransactionFilters): string {
  const params = new URLSearchParams();
  if (filters.account_id) params.set("account_id", filters.account_id);
  if (filters.category) params.set("category", filters.category);
  if (filters.from) params.set("from", filters.from);
  if (filters.to) params.set("to", filters.to);
  if (filters.limit != null) params.set("limit", String(filters.limit));
  if (filters.offset != null) params.set("offset", String(filters.offset));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useTransactions(filters: TransactionFilters) {
  return useQuery({
    queryKey: ["transactions", filters],
    queryFn: () => apiFetch<TransactionList>(`/api/v1/transactions${buildQuery(filters)}`),
  });
}

export function useCreateTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TransactionCreate) =>
      apiFetch<unknown>("/api/v1/transactions", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow"] });
    },
  });
}

export function useUpdateTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<TransactionCreate> }) =>
      apiFetch<Transaction>(`/api/v1/transactions/${id}`, {
        method: "PUT",
        body: JSON.stringify(patch),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow"] });
    },
  });
}

export function useMonthlySummaries() {
  return useQuery({
    queryKey: ["cashflow", "summary"],
    queryFn: () => apiFetch<MonthlySummary[]>("/api/v1/cashflow/summary"),
  });
}

export function useProjection() {
  return useQuery({
    queryKey: ["cashflow", "projection"],
    queryFn: () => apiFetch<CashflowProjection>("/api/v1/cashflow/projection"),
  });
}

export function useAlerts() {
  return useQuery({
    queryKey: ["cashflow", "alerts"],
    queryFn: () => apiFetch<Alert[]>("/api/v1/cashflow/alerts"),
  });
}

// Import de extrato: corpo cru (texto do arquivo) — apiFetch força JSON, então
// usamos fetch direto com o Bearer em memória.
export function useImportStatement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ accountId, file }: { accountId?: string; file: File }) => {
      const text = await file.text();
      const token = getAccessToken();
      const acct = accountId ? `&account_id=${accountId}` : "";
      const res = await fetch(
        `${API_BASE_URL}/api/v1/ledger/import?filename=${encodeURIComponent(file.name)}${acct}`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "text/plain",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: text,
        },
      );
      if (!res.ok) throw new ApiError(res.status, `Import failed with ${res.status}`);
      return (await res.json()) as ImportReport;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow"] });
    },
  });
}
