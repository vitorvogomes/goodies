// Tipos do Market Engine (m3) — espelham engines/market/models.py (PriceOut).

export interface Price {
  ticker: string;
  price_brl: number | null;
  price_usd: number | null;
  source: string | null;
  is_manual: boolean;
  stale: boolean;
  last_updated: string | null; // ISO8601 ou null
}

export interface PricesResponse {
  prices: Price[];
}
