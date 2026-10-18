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
