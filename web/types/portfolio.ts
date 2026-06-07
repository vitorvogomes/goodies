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
  // null em cripto (m4): o custo é conhecido só no nível do sleeve, não por ativo
  preco_medio: number | null;
  custo_total: number | null;
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

// Crypto sleeve (m4): custo (ledger) x valor atual (carteiras). Custo/resultado/XIRR só no
// nível do sleeve — cripto não vive em asset_operations. Serve também a reconciliação de valor.
export interface CryptoSleeveRail {
  rail: string;
  current_value_brl: number;
}

export interface CryptoSleeveCategory {
  category: string;
  net_invested_brl: number;
}

export interface CryptoSleeve {
  current_value_brl: number;
  cost_basis_brl: number;
  returned_brl: number;
  net_invested_brl: number;
  resultado: number;
  xirr: number | null;
  by_rail: CryptoSleeveRail[];
  by_category: CryptoSleeveCategory[];
  stale_value: boolean;
}

export interface OperationFilters {
  asset_symbol?: string;
  tipo?: OperationTipo;
  data_from?: string;
  data_to?: string;
}
