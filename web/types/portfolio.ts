// Tipos TypeScript do Portfolio Engine (m2), espelhando as respostas do FastAPI.

export type OperationTipo =
  | "compra"
  | "venda"
  | "dividendo"
  | "juros"
  | "aporte"
  | "resgate";

export interface AssetOperation {
  id: string;
  user_id: string;
  broker: string;
  asset_symbol: string;
  asset_category: string;
  tipo: OperationTipo;
  quantidade: number;
  valor_unitario: number;
  data_operacao: string;
  notes: string | null;
  external_id: string | null;
  created_at: string;
}

export interface Position {
  asset_symbol: string;
  asset_category: string;
  quantidade_net: number;
  preco_medio: number;
  custo_total: number;
  preco_atual: number | null;
  valor_atual: number | null;
  resultado: number | null;
  resultado_pct: number | null;
  stale: boolean;
  is_manual: boolean; // false = preço capturado via Market Engine (edição bloqueada)
}

export interface AllocationCategory {
  category: string;
  valor_atual: number;
  pct_atual: number;
  pct_meta: number | null;
  desvio_pp: number | null;
}

export interface Allocation {
  total: number;
  categories: AllocationCategory[];
}

export interface Rebalancing {
  contribution: number;
  suggestions: Record<string, number>;
  current_allocation: Record<string, number>;
  target_allocation: Record<string, number>;
  deviations_pp: Record<string, number>;
  message?: string;
}

export interface XIRR {
  consolidated: number | null;
  by_category: Record<string, number | null>;
  by_asset: Record<string, number | null>;
  calculated_at: string;
}

export interface OperationFilters {
  asset_symbol?: string;
  tipo?: OperationTipo;
  data_from?: string;
  data_to?: string;
}
