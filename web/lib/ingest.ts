"use client";

// Hooks do Hub de import (Story 3.9): Bloco Fontes, prévia (multiarquivo), nova prévia com escolhas
// e confirmação — queryKey [engine, recurso] (AD-17).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
import type {
  ImportConfirmed,
  ImportHistory,
  ImportPreview,
  SourceRow,
  UndoPreview,
} from "@/types/ingest";

export function useSources() {
  return useQuery({
    queryKey: ["ingest", "sources"],
    queryFn: () => apiFetch<SourceRow[]>("/api/v1/ingest/sources"),
  });
}

export function usePreviewImport() {
  return useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData();
      for (const f of files) form.append("files", f, f.name);
      return apiFetch<ImportPreview>("/api/v1/ingest/preview", { method: "POST", body: form });
    },
  });
}

export function useReplanImport() {
  return useMutation({
    mutationFn: (body: { batch_id: string; overrides: Record<string, Record<string, string>> }) =>
      apiFetch<ImportPreview>("/api/v1/ingest/replan", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

export function useConfirmImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { batch_id: string; hash: string }) =>
      apiFetch<ImportConfirmed>("/api/v1/ingest/confirm", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: async () => {
      await invalidateAfter(queryClient, "ingest", "ledger", "market");
    },
  });
}

// ---- Histórico de imports e desfazer o último lote (Story 3.14) ----

export function useImportHistory() {
  return useQuery({
    queryKey: ["ingest", "batches"],
    queryFn: () => apiFetch<ImportHistory>("/api/v1/ingest/batches"),
  });
}

export function useUndoPreview(batchId: string | null) {
  return useQuery({
    // Fora de "ingest": desfeito o lote, a invalidação não deve repedir a prévia (daria 409).
    queryKey: ["undo-preview", batchId],
    queryFn: () =>
      apiFetch<UndoPreview>(`/api/v1/ingest/batches/${batchId}/undo/preview`, { method: "POST" }),
    enabled: batchId !== null,
  });
}

export function useUndoBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) =>
      apiFetch<UndoPreview>(`/api/v1/ingest/batches/${batchId}/undo`, { method: "POST" }),
    onSuccess: async () => {
      // desfazer um consolidado B3 também devolve o preço anterior
      await invalidateAfter(queryClient, "ingest", "ledger", "market");
    },
  });
}
