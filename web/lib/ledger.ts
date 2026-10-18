"use client";

// Hooks React Query do Ledger (m1) — wrappers sobre apiFetch.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
import type {
  Account,
  Alert,
  CashflowProjection,
  Category,
  CategoryBreakdown,
  CategoryCreate,
  CategoryGroupNode,
  CategoryKind,
  CategoryOption,
  CategoryUpdate,
  FixedCost,
  FixedCostCreate,
  GroupKind,
  ImportReport,
  LedgerTransaction,
  MonthlySummary,
  Page,
  Suggestion,
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

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CategoryCreate) =>
      apiFetch<Category>("/api/v1/categories", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["categories"] }),
  });
}

export function useUpdateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: CategoryUpdate }) =>
      apiFetch<Category>(`/api/v1/categories/${id}`, {
        method: "PUT",
        body: JSON.stringify(patch),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["categories"] }),
  });
}

export function useDeleteCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/categories/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["categories"] }),
  });
}

export function useCategoryBreakdown(month?: string) {
  return useQuery({
    queryKey: ["cashflow", "by-category", month ?? "all"],
    queryFn: () =>
      apiFetch<CategoryBreakdown>(
        `/api/v1/cashflow/by-category${month ? `?month=${month}` : ""}`,
      ),
  });
}

export function useFixedCosts(active?: boolean) {
  return useQuery({
    queryKey: ["fixed-costs", active ?? "all"],
    queryFn: () =>
      apiFetch<FixedCost[]>(
        `/api/v1/fixed-costs${active != null ? `?active=${active}` : ""}`,
      ),
  });
}

export function useCreateFixedCost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FixedCostCreate) =>
      apiFetch<FixedCost>("/api/v1/fixed-costs", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fixed-costs"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow"] });
    },
  });
}

export function useUpdateFixedCost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<FixedCostCreate> }) =>
      apiFetch<FixedCost>(`/api/v1/fixed-costs/${id}`, {
        method: "PUT",
        body: JSON.stringify(patch),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fixed-costs"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow"] });
    },
  });
}

export function useDeleteFixedCost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/fixed-costs/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fixed-costs"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow"] });
    },
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

// D — sugestões de categoria p/ despesas em "outros". Key sob ["transactions"] para
// ser invalidada automaticamente quando uma transação é atualizada (confirmar).
export function useSuggestions() {
  return useQuery({
    queryKey: ["transactions", "suggestions"],
    queryFn: () => apiFetch<Suggestion[]>("/api/v1/transactions/suggestions"),
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

// Import de extrato: corpo cru (texto do arquivo) via apiFetch com Content-Type text/plain
// — herda o interceptor 401→refresh→retry (antes era fetch cru, sem refresh do access).
export function useImportStatement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ accountId, file }: { accountId?: string; file: File }) => {
      const text = await file.text();
      const acct = accountId ? `&account_id=${accountId}` : "";
      const path = `/api/v1/ledger/import?filename=${encodeURIComponent(file.name)}${acct}`;
      return apiFetch<ImportReport>(path, {
        method: "POST",
        body: text,
        headers: { "Content-Type": "text/plain" },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow"] });
    },
  });
}

// ---- v2: Caixa › Transações (Story 2.7) — queryKey [engine, recurso, periodo] (AD-17) ----

export function useLedgerTransactions(periodo: string) {
  return useQuery({
    queryKey: ["ledger", "transactions", periodo],
    queryFn: () =>
      apiFetch<Page<LedgerTransaction>>(`/api/v1/ledger/transactions?periodo=${periodo}&limit=1000`),
  });
}

export function useCategoryOptions(includeArchived = false) {
  return useQuery({
    queryKey: ["ledger", "categories", includeArchived],
    queryFn: () =>
      apiFetch<CategoryOption[]>(
        `/api/v1/ledger/categories${includeArchived ? "?incluir_arquivadas=true" : ""}`,
      ),
  });
}

export function useSetTransactionCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, categoryId }: { id: string; categoryId: string }) =>
      apiFetch<LedgerTransaction>(`/api/v1/ledger/transactions/${id}/category`, {
        method: "PATCH",
        body: JSON.stringify({ category_id: categoryId }),
      }),
    onSuccess: () => invalidateAfter(queryClient, "ledger"),
  });
}

// ---- v2: lançamento manual (Story 2.8) ----

export interface ManualTransactionIn {
  account_id: string;
  date: string;
  amount: string; // decimal em string (AD-4)
  description: string | null;
  category_id: string;
}

export function useSaveManualTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Partial<ManualTransactionIn> }) =>
      apiFetch<LedgerTransaction>(`/api/v1/ledger/transactions${id ? `/${id}` : ""}`, {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => invalidateAfter(queryClient, "ledger"),
  });
}

export function useDeleteManualTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/ledger/transactions/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateAfter(queryClient, "ledger"),
  });
}

// ---- v2: Ajustes › Categorias (Story 2.9) ----

export function useCategoryTree(includeArchived: boolean) {
  return useQuery({
    queryKey: ["ledger", "category-tree", includeArchived],
    queryFn: () =>
      apiFetch<CategoryGroupNode[]>(
        `/api/v1/ledger/category-tree${includeArchived ? "?incluir_arquivadas=true" : ""}`,
      ),
  });
}

type CategoryMutation =
  | { op: "create-group"; body: { name: string; kind: GroupKind } }
  | { op: "update-group"; id: string; body: Partial<{ name: string; kind: GroupKind; is_active: boolean }> }
  | { op: "create"; body: { name: string; group_id: string; role?: string } }
  | { op: "update"; id: string; body: Partial<{ name: string; group_id: string; role: string; is_active: boolean }> }
  | { op: "delete"; id: string };

export function useCategoryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (m: CategoryMutation) => {
      const base = "/api/v1/ledger";
      switch (m.op) {
        case "create-group":
          return apiFetch(`${base}/category-groups`, { method: "POST", body: JSON.stringify(m.body) });
        case "update-group":
          return apiFetch(`${base}/category-groups/${m.id}`, { method: "PATCH", body: JSON.stringify(m.body) });
        case "create":
          return apiFetch(`${base}/categories`, { method: "POST", body: JSON.stringify(m.body) });
        case "update":
          return apiFetch(`${base}/categories/${m.id}`, { method: "PATCH", body: JSON.stringify(m.body) });
        case "delete":
          return apiFetch(`${base}/categories/${m.id}`, { method: "DELETE" });
      }
    },
    onSuccess: () => invalidateAfter(queryClient, "ledger"),
  });
}
