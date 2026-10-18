// Tipos TypeScript do Portfolio Engine (m2), espelhando as respostas do FastAPI.

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

export interface XIRR {
  consolidated: number | null;
  by_category: Record<string, number | null>;
  by_asset: Record<string, number | null>;
  calculated_at: string;
}
