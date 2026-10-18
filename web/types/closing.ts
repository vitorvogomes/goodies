// Fechamento de mês (Stories 5.3–5.5).
export type MonthStatus = "aberto" | "fechado" | "ajuste";

export interface MonthState {
  month: string; // "2026-09-01"
  status: MonthStatus;
  version: number | null;
  closed_at: string | null;
  origin: "live" | "retro" | null;
}

export interface ChecklistItem {
  key: string;
  code: string | null;
  ok: boolean;
  kind: "bloqueia" | "confirma" | "info";
  message: string;
}

export interface MonthSummary {
  month: string;
  as_of: string;
  source: string;
  receitas: number;
  gastos: number;
  investido: number;
  resultado_mes: number;
  taxa_poupanca: number | null;
  patrimonio: number;
  valor_investido: number;
  resultado_investimentos: number;
  rentabilidade: number | null;
  coverage: Record<string, string>;
}

export interface Checklist {
  month: string;
  items: ChecklistItem[];
  blocking: number;
  pending: number;
  summary: MonthSummary;
}

export interface ReopenRow {
  metric: string;
  label: string;
  frozen: number | null;
  live: number | null;
}

export interface ReopenPreview {
  month: string;
  version: number;
  rows: ReopenRow[];
}

export interface RecoveryStep {
  key: "importar" | "revisar" | "conferir" | "fechar";
  label: string;
  state: "feito" | "atual" | "a_fazer";
  detail: string | null;
  href: string | null;
}

export interface Recovery {
  active: boolean;
  base_until: string | null;
  message: string | null;
  months: { month: string; status: MonthStatus }[];
  current: string | null;
  steps: RecoveryStep[];
}

// Visão geral › Histórico (Story 9.1).
export interface HistoryRow {
  key: string;
  label: string;
  kind: "money" | "pct";
  current: number | null;
  previous: number | null;
  average: number | null;
  var_previous: number | null;
  var_average: number | null;
}

export interface History {
  periodo: string;
  leitura: string;
  months: { month: string; source: "live" | "snapshot" }[];
  as_of: string | null;
  stale: boolean;
  previous_label: string | null;
  average_months: number;
  rows: HistoryRow[];
  groups: HistoryRow[];
}
