// Fechamento de mês (Stories 5.3–5.5).
import type { Valued } from "@/types/overview";

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

// Visão geral › Histórico — crescimento do patrimônio (Story 9.2).
export interface GrowthAsset {
  symbol: string;
  cls: string;
  xirr_mensal: number | null;
  resultado: number | null;
}

export interface Growth {
  periodo: string;
  leitura: string;
  available: boolean;
  reason: "antes_do_primeiro_fechamento" | "patrimonio_nao_coberto" | null;
  start_value: number | null;
  end_value: number | null;
  crescimento: number | null;
  aporte: number | null;
  resultado: number | null;
  classes: {
    key: string;
    label: string;
    xirr_nominal: Valued;
    resultado: number | null;
    xirr_mensal: number | null; // o XIRR nominal ao mês
  }[];
  assets: GrowthAsset[];
  best: GrowthAsset | null;
  worst: GrowthAsset | null;
}

// Séries dos gráficos do Histórico (Story 9.3).
export interface SeriesPoint {
  month: string;
  source: "live" | "snapshot";
  patrimonio: number | null;
  aplicado: number | null;
  planejado: number | null;
  realizado: number;
}

export interface Series {
  points: SeriesPoint[];
  realizado_media12: number | null;
}
