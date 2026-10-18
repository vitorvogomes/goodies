// Hub de import (Stories 3.3 e 3.9) — protocolo de prévia → confirmação da engine ingest.
export interface FilePlan {
  source: string | null;
  file_name: string;
  file_hash: string;
  account_id: string | null;
  account_name: string | null;
  broker: string | null;
  period_start: string | null;
  period_end: string | null;
  new: number;
  existing: number;
  skipped: number;
  reported_balance: number | null;
  reported_balance_date: string | null;
  already_imported: boolean;
  needs: string[];
  warnings: string[];
  error: string | null;
  detail: Record<string, unknown>;
}

export interface ImportPreview {
  batch_id: string;
  hash: string;
  expires_at: string;
  files: FilePlan[];
  new: number;
}

export interface ImportConfirmed {
  batch_id: string;
  imported: number;
  files: FilePlan[];
}

export interface SourceRow {
  key: string;
  label: string;
  kind: string;
  updated_until: string | null;
  stale: boolean;
  balance_status: "conferido" | "divergente" | null;
  balance_as_of: string | null;
  balance_difference: number | null;
}

// ---- Histórico de imports e desfazer (Story 3.14) ----
export interface HistoryBatch {
  id: string;
  status: "applied" | "undone" | "legacy";
  created_at: string;
  applied_at: string | null;
  files: { source: string; file_name: string | null; period_start: string | null; period_end: string | null }[];
  new: number | null;
  undoable: boolean;
}

export interface ImportHistory {
  items: HistoryBatch[];
  undo_note: string | null;
}

export interface UndoPreview {
  batch_id: string;
  applied_at: string;
  transactions: number;
  operations: number;
  categorizations: number;
  rules: number;
  balances: number;
  snapshots: number;
  prices: number;
  closed_months?: string[]; // "AAAA-MM" dos meses fechados que o desfazer ajusta
}
