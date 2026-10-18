"use client";

// Hooks do Hub de import (Story 3.9): Bloco Fontes, prévia (multiarquivo), nova prévia com escolhas
// e confirmação — queryKey [engine, recurso] (AD-17).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { invalidateAfter } from "@/lib/invalidate";
import type { ImportConfirmed, ImportPreview, SourceRow } from "@/types/ingest";

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
      await invalidateAfter(queryClient, "ingest");
      await invalidateAfter(queryClient, "ledger");
      // telas v1 ainda leem estas chaves
      await queryClient.invalidateQueries({ queryKey: ["transactions"] });
      await queryClient.invalidateQueries({ queryKey: ["cashflow"] });
      await queryClient.invalidateQueries({ queryKey: ["market"] });
    },
  });
}
