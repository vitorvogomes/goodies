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
  resgates_itens: { date: string; description: string; value: number }[];
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
  restante_sem_resgates: Valued;
  gastos: number;
  deducao_fixos: number;
  deducao_dividas: number;
  devolucoes: number;
  investido: number;
  taxa_poupanca: Valued;
  aporte_sobre_trabalho: Valued;
  consumido_por_grupo: ConsumedGroup[];
}
