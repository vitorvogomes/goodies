// Frescor dos jobs de atualização (Pilar 0) — espelha engines/jobs/router.py.
export interface JobStatus {
  job: string;
  last_run: string | null; // ISO8601 ou null (nunca rodou)
  ok: boolean | null;
  error: string | null;
  stale: boolean;
  age_seconds: number | null;
}
