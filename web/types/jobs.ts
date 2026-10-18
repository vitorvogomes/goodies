// Frescor dos jobs de atualização (Pilar 0) — espelha engines/jobs/router.py.
export type JobState = "fresh" | "stale" | "error" | "partial";

export interface JobStatus {
  job: string;
  label: string; // Story 10.3: o nome na tela
  note: string | null;
  last_run: string | null; // ISO8601 ou null (nunca rodou)
  last_success_at: string | null;
  next_run: string | null;
  ok: boolean | null;
  error: string | null;
  stale: boolean;
  age_seconds: number | null;
  data_age_seconds: number | null; // wallet_scan: idade real do scanned_at
  stats: Record<string, unknown> | null;
  status: JobState;
}
