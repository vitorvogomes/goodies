// Formatadores pt-BR para a UI do Ledger (m1).

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

export function formatBRL(value: number): string {
  return BRL.format(value);
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1).replace(".", ",")}%`;
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
