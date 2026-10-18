// Investimentos › Posições (Story 7.1) — da rota de `closing` (AD-8).
import type { Valued } from "@/types/overview";

export interface PositionAsset {
  symbol: string;
  aplicado: number | null;
  valor: Valued;
  resultado: number | null;
  manual: boolean;
  xirr_mensal: number | null; // % a.m. do período (RF e cripto não têm)
  nota: string | null; // RF: "{x}% do CDI · CDI até dd/mm/aaaa"
}

export interface PositionClass {
  key: string;
  label: string;
  is_bucket: boolean;
  aplicado: number | null;
  valor: number;
  resultado: number | null;
  assets: PositionAsset[];
  xirr_nominal: Valued;
  xirr_real: Valued;
}

export interface PositionsReport {
  periodo: string;
  leitura: string;
  as_of: string;
  months: { month: string; source: "live" | "snapshot" }[];
  classes: PositionClass[];
  aplicado: number;
  valor: number;
  xirr_nominal: Valued;
  xirr_real: Valued;
  ipca_ate: string | null;
}

// Ajustes › Debêntures (Story 7.6).
export interface Debenture {
  id: string;
  asset_id: string;
  symbol: string;
  issuer: string;
  rate_label: string;
  monthly_factor: number;
  start_date: string;
  maturity_date: string | null;
  aplicado: number;
}

export interface DebentureIn {
  issuer?: string;
  rate_label?: string;
  monthly_factor?: string; // "1.78" (% a.m.)
  start_date?: string;
  maturity_date?: string | null;
}
