// Tipos do Wallet Engine (m4) — espelham engines/wallet/router.py + defi_router.py.

export interface WalletPosition {
  chain: string;
  wallet_address: string;
  asset_symbol: string;
  quantity: number;
  source: string;
  scanned_at: string; // ISO8601
  price_brl: number | null;
  price_usd: number | null;
  value_brl: number | null;
  value_usd: number | null;
  stale: boolean;
  is_manual: boolean;
}

export interface Reconciliation {
  asset_symbol: string;
  scanned_quantity: number;
  registered_quantity: number;
  delta: number;
  value_brl: number | null;
  value_usd: number | null;
}

export interface DefiPosition {
  id: string;
  asset_symbol: string;
  balance: number;
  protocol: string | null;
  maturity_date: string | null; // "YYYY-MM-DD" ou null
  is_active: boolean;
  notes: string | null;
  price_brl: number | null;
  price_usd: number | null;
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
}

export interface DefiPositionInput {
  asset_symbol: string;
  balance: number;
  protocol?: string | null;
  maturity_date?: string | null;
  is_active?: boolean;
  notes?: string | null;
}
