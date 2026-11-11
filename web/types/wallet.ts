// Tipos do Wallet Engine (m4) — espelham engines/wallet/router.py + defi_router.py.

export interface Reconciliation {
  asset_symbol: string;
  scanned_quantity: number;
  registered_quantity: number;
  delta: number;
  value_brl: number | null;
  value_usd: number | null;
}

export interface ManualPositionInput {
  chain: string;
  asset_symbol: string;
  quantity: number;
  as_of?: string | null; // a data em que o Vitor viu a posição (Story 7.8)
}

export interface ManualItem {
  kind: "carteira" | "defi";
  id: string;
  asset_symbol: string;
  quantity: number;
  chain: string | null;
  protocol: string | null;
  as_of: string | null;
  maturity_date: string | null;
  notes: string | null;
  is_active: boolean;
  // v2.2: valor de hoje e, no DeFi, o saldo em US$ informado (o preço do token sai dele)
  value_brl?: number | null;
  value_usd?: number | null;
  anchor?: DefiAnchor | null;
}

export interface DefiAnchor {
  as_of: string;
  value_usd: number;
  apy: number | null; // % a.a.
}

export interface DefiBalanceInput {
  as_of: string;
  value_usd: string; // decimal em texto (AD-4)
  apy: string | null;
}

export interface DefiPositionInput {
  asset_symbol: string;
  balance: number;
  protocol?: string | null;
  maturity_date?: string | null;
  is_active?: boolean;
  notes?: string | null;
}
