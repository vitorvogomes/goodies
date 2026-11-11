// Painel principal (Stories 4.1 e 4.2) — `Valued` da AD-15.
import type { SourceRow } from "@/types/ingest";
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
  /** Um insumo estimado (ex.: IPCA do mês que ainda não saiu = o último publicado). */
  estimated?: boolean;
}

export interface Painel {
  periodo: string;
  resultado_mes: Valued;
  resultado_mes_anterior: Valued;
  variacao_resultado_mes: Valued;
  patrimonio: Valued;
  resultado_investimentos: Valued;
  rentabilidade_nominal: Valued;
  rentabilidade_real: Valued;
  a_revisar: number;
}

export interface Fonte extends SourceRow {
  opens_hub: boolean;
}
