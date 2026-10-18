// Período na URL (Story 1.8 — AD-14, UX-DR8): `periodo=YYYY-MM` + `leitura ∈ {mes, tri, ano, inicio}`.
// Espelha `common.dates.resolve_period` do backend. Nenhum mês anterior a jul/2024 (início da base)
// nem futuro; "hoje" é o mês corrente em São Paulo.

export type Leitura = "mes" | "tri" | "ano" | "inicio";
export const LEITURAS: readonly Leitura[] = ["mes", "tri", "ano", "inicio"];
export const MIN_MONTH = "2024-07";

const RE = /^(\d{4})-(0[1-9]|1[0-2])$/;

export function currentMonthBRT(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
  }).formatToParts(now);
  const year = parts.find((p) => p.type === "year")?.value;
  const month = parts.find((p) => p.type === "month")?.value;
  return `${year}-${month}`;
}

export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const index = y * 12 + (m - 1) + delta;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

export function isSelectable(month: string, now: Date = new Date()): boolean {
  return RE.test(month) && month >= MIN_MONTH && month <= currentMonthBRT(now);
}

/** Período efetivo da URL: ausente/inválido → mês atual; antes de jul/2024 → jul/2024; futuro → atual. */
export function normalizePeriodo(raw: string | null | undefined, now: Date = new Date()): string {
  const current = currentMonthBRT(now);
  if (!raw || !RE.test(raw)) return current;
  if (raw < MIN_MONTH) return MIN_MONTH;
  if (raw > current) return current;
  return raw;
}

export function parseLeitura(raw: string | null | undefined): Leitura {
  return LEITURAS.includes(raw as Leitura) ? (raw as Leitura) : "mes";
}

function range(from: string, to: string): string[] {
  const out: string[] = [];
  for (let m = from; m <= to; m = shiftMonth(m, 1)) out.push(m);
  return out;
}

/** Meses da leitura, ancorada no período e nunca depois dele (nem antes de jul/2024). */
export function resolvePeriod(periodo: string, leitura: Leitura): string[] {
  const [y, m] = periodo.split("-").map(Number);
  const start = {
    mes: periodo,
    tri: `${y}-${String(Math.floor((m - 1) / 3) * 3 + 1).padStart(2, "0")}`,
    ano: `${y}-01`,
    inicio: MIN_MONTH,
  }[leitura];
  return range(start < MIN_MONTH ? MIN_MONTH : start, periodo);
}
