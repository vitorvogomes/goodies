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
