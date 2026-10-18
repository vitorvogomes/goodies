// Orçamento do mês (Stories 6.5–6.7) — tudo vem da API (AD-4/AD-15).
import type { Valued } from "@/types/overview";

export interface ConsumedSub {
  name: string;
  value: number;
  pct: number;
  count: number;
}

export interface ConsumedGroup {
  group: string;
  value: number;
  pct: number;
  count: number;
  subcategories: ConsumedSub[];
}

export interface MonthBudget {
  month: string;
  as_of: string | null;
  source: "live" | "snapshot";
  closed: boolean;
  trabalho: Valued;
  trabalho_por_pagador: { payer: string; value: number }[];
  resgates: Valued;
  resgates_itens: { date: string; description: string; value: number; goal: string | null }[];
  custos_fixos: Valued;
  custos_fixos_pagos: number;
  custos_fixos_a_pagar: number;
  aporte_planejado: number;
  aporte_definido: boolean;
  dividas: number;
  dividas_informadas: boolean;
  dividas_prefill: number;
  disponivel: Valued;
  consumido: Valued;
  restante: Valued;
  consumo_financiado: Valued;
  financiado_objetivo: Valued; // Story 8.1: por objetivo (neutro)
  financiado_carteira: Valued; // por resgate da carteira (laranja)
  restante_sem_resgates: Valued;
  gastos: number;
  deducao_fixos: number;
  deducao_dividas: number;
  devolucoes: number;
  investido: number;
  taxa_poupanca: Valued;
  aporte_sobre_trabalho: Valued;
  consumido_por_grupo: ConsumedGroup[];
  grupos_total: number;
  detalhe: boolean; // false: fechado antes do orçamento — só os totais congelados
}

// Ajustes › Objetivos (Story 8.1).
export interface GoalAsset {
  asset_id: string;
  label: string;
  valor: number | null;
  aportado: number;
}

export interface Goal {
  id: string;
  kind: "reserva" | "objetivo";
  name: string;
  target: number;
  deadline: string | null;
  multiplier: number | null;
  horizon_months: number | null;
  assets: GoalAsset[];
  valor: number;
  aportado: number;
  progress: number;
}

export interface GoalSuggestion {
  asset_id: string;
  label: string;
  goal_id: string | null;
  goal_name: string | null;
}

export interface GoalsOut {
  goals: Goal[];
  suggestions: GoalSuggestion[];
}

export interface GoalIn {
  name?: string;
  target?: string;
  deadline?: string;
  asset_ids?: string[];
  multiplier?: string;
  horizon_months?: number;
}

// Ajustes › Metas (Story 8.2).
export interface TargetAsset {
  asset_id: string;
  label: string;
  pct: number;
}

export interface TargetClass {
  cls: string;
  label: string;
  pct: number;
  band_pp: number;
  floor: number;
  assets: TargetAsset[];
}

export interface TargetsOut {
  defined: boolean;
  valid_from: string | null;
  classes: TargetClass[];
}

export interface TargetsIn {
  classes: {
    cls: string;
    pct: string;
    band_pp: string;
    floor: string;
    assets: { asset_id: string; pct: string }[];
  }[];
}

export interface TargetsPreview {
  ok: boolean;
  errors: { level: string; total: number; message: string }[];
}

// Distribuição do aporte (Story 8.5) — POST /api/v1/planning/distribution/preview.
export interface DistributionAsset {
  id: string;
  label: string;
  meta: number | null;
  atual: number;
  sugerido: number | null;
  locked: boolean;
  realizado: number;
  pendente: number | null;
}

export interface DistributionClass {
  cls: string;
  label: string;
  meta: number;
  atual: number;
  desvio: number;
  banda: number;
  floor: number;
  sugerido: number;
  floor_only: boolean;
  out_of_band: boolean;
  locked: boolean;
  assets: DistributionAsset[];
  realizado: number;
  pendente: number;
}

export interface DistributionGoal {
  id: string;
  name: string;
  kind: "reserva" | "objetivo";
  target: number;
  current: number;
  progress: number;
  deadline: string | null;
  monthly: number;
  sugerido: number;
  locked: boolean;
  realizado: number;
  pendente: number;
}

export interface Andamento {
  planned: number;
  realizado: number;
  em_ativo: number;
  a_caminho: number;
  pendente: number;
  pct_realizado: number | null;
  sugerido_linhas: number;
  pendente_linhas: number;
  confere: boolean;
  pct_em_ativo: number;
  pct_a_caminho: number;
}

export interface Distribution {
  month: string;
  aporte_definido: boolean;
  planned: number;
  goals: DistributionGoal[];
  classes: DistributionClass[];
  floors_reduced: boolean;
  locks_total: number;
  locks_over: boolean;
  has_targets: boolean;
  unassigned: number;
  andamento: Andamento;
}
