// Painel principal (Story 4.1) — `Valued` da AD-15.
export type UnavailableReason =
  | "nao_definido"
  | "aguardando_ipca"
  | "antes_do_primeiro_fechamento"
  | "sem_preco"
  | "sem_metas"
  | "sem_receita"
  | "fora_do_resumo";

export interface Valued {
  value: number | null;
  unavailable_reason: UnavailableReason | null;
  as_of: string | null;
  source: string | null;
  stale: boolean;
}

export interface Painel {
  periodo: string;
  resultado_mes: Valued;
  resultado_mes_anterior: Valued;
  patrimonio: Valued;
  resultado_investimentos: Valued;
  rentabilidade_nominal: Valued;
}
