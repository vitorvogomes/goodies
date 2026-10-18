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
  asset_id: string | null;
  alocacao: number | null; // Story 8.3: % do ativo na classe
  meta: number | null;
  desvio_pp: number | null;
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
  alocacao: number | null; // Story 8.3: % na base (sem os objetivos)
  meta: number | null;
  banda: number | null;
  desvio_pp: number | null;
  fora_banda: boolean;
}

export interface PositionsReport {
  periodo: string;
  leitura: string;
  as_of: string;
  months: { month: string; source: "live" | "snapshot" }[];
  classes: PositionClass[];
  aplicado: number;
  valor: number;
  caixa_corretora: number; // no patrimônio (Story 7.7)
  total: number; // posições + caixa em corretora
  a_caminho: { broker: string; value: number; import_from: string | null }[]; // fora do patrimônio
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

// Integralização da debênture (P17): a operação de aporte, editável.
export interface DebentureContribution {
  id: string;
  data: string;
  valor: number;
  saldo: number; // valor hoje pela taxa
  transacao: string | null; // a saída da conta ligada, se houver
}

export interface DebentureIn {
  issuer?: string;
  rate_label?: string;
  monthly_factor?: string; // "1.78" (% a.m.)
  start_date?: string;
  maturity_date?: string | null;
}

// Investimentos › Conciliação — Cartão de corretora (Story 7.7).
export interface BrokerCard {
  rail: string;
  name: string;
  saiu: number;
  proventos: number;
  aplicado: number;
  caixa: number;
  a_caminho: number;
  covered_until: string | null;
  import_from: string | null;
  informed: number | null;
  informed_at: string | null;
  caixa_at_check: number | null; // o caixa calculado na data do saldo informado
  divergent: boolean;
}

// Investimentos › Conciliação — app × consolidado B3 × carteiras (Story 7.9, AD-13). Quantidades
// chegam como texto decimal da API.
export type ReconStatus = "conferido" | "divergente" | "valor calculado";

export interface ReconRow {
  symbol: string;
  cls: string;
  app: string;
  origin: string | null;
  diff: string | null;
  status: ReconStatus;
}

export interface Reconciliation {
  b3: { ref_date: string | null; rows: ReconRow[] };
  wallets: { scanned_at: string | null; attempt_at: string | null; stale: boolean; rows: ReconRow[] };
  all_ok: boolean;
}
