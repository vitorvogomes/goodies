// Formatadores pt-BR para a UI do Ledger (m1).

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

export function formatBRL(value: number): string {
  return BRL.format(value);
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1).replace(".", ",")}%`;
}

// Taxa decimal -> percentual com 2 casas (ex: 0.0853 -> "8,53%"). null -> "—".
export function formatRate(value: number | null): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(2).replace(".", ",")}%`;
}

// Pontos percentuais com sinal (ex: -2.4 -> "-2,4pp", 8.7 -> "+8,7pp").
export function formatPP(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1).replace(".", ",")}pp`;
}

export function formatDate(iso: string): string {
  // "2026-06-04" -> "04/06/2026"
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
}

export function formatMonth(month: string): string {
  // "2026-06" -> "jun/2026"
  const [year, month_] = month.split("-");
  return `${MONTHS[Number(month_) - 1] ?? month_}/${year}`;
}
