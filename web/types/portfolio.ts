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
  custody?: string | null;
  // cripto entra como UMA linha-bloco (sleeve), fora da tabela per-ativo (renderizada como card)
  is_bucket?: boolean;
  quantidade_net: number | null; // null no bloco cripto
  // null no bloco cripto (m4): custo/preço médio vivem no nível do sleeve
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
  current_value_usd: number;
  usd_partial: boolean;
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

// Import B3 (A4): relatório consolidado / movimentação / negociação -> asset_operations.
// skipped_overlap = trades cujo período já está coberto por outra fonte (regra de
// cobertura; evita dobrar trade-vs-liquidação). new_tickers = pedem confirmação.
export interface ImportB3Report {
  file_type: string;
  parsed: number;
  imported: number;
  skipped_duplicate: number;
  skipped_overlap: number;
  overlap_tickers: string[];
  new_tickers: string[];
  date_range: [string, string] | null;
  prices_upserted: number;
  prices_skipped_manual: number;
  dry_run: boolean;
  note?: string | null;
}

// Reconciliação de trânsito (Pilar 2): saiu do Nubank vs virou posição, por trilho.
// Rendimentos (dividendo/juros) separados do ganho de capital — GET /portfolio/income.
export interface IncomeByAsset {
  asset_symbol: string;
  asset_category: string;
  total: number;
}
export interface IncomeByCategory {
  asset_category: string;
  total: number;
}
export interface Income {
  total: number;
  by_asset: IncomeByAsset[];
  by_category: IncomeByCategory[];
  by_type: Record<string, number>;
}

export type TransitStatus = "reconciled" | "pending" | "rendimento_realizado";

export interface TransitRail {
  rail: string;
  saiu_brl: number;
  aplicado_brl: number;
  em_transito_brl: number;
  dividendos_juros_brl: number;
  caixa_corretora_brl: number | null;
  status: TransitStatus;
}

export interface TransitCrypto {
  net_invested_brl: number;
  current_value_brl: number;
  resultado_brl: number;
}

export interface Transit {
  rails: TransitRail[];
  crypto: TransitCrypto;
}
