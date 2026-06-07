// Formatadores pt-BR para a UI do Ledger (m1).

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const USD = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

export function formatBRL(value: number): string {
  return BRL.format(value);
}

// Valor em dólar (ex.: 280 -> "$280.00"). Usado nas carteiras cripto (m4).
export function formatUSD(value: number): string {
  return USD.format(value);
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

// Quantidade com até 8 casas (pt-BR). Compartilhado por carteiras/reconciliação (m4).
export function fmtQty(n: number): string {
  return n.toLocaleString("pt-BR", { maximumFractionDigits: 8 });
}

// ISO -> "dd/mm/aaaa hh:mm" (pt-BR). null/inválido -> "—".
export function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

// Converte número digitado (pt-BR ou en) em Number, tratando separador de milhar.
// "1.234,56"->1234.56 · "1234,56"->1234.56 · "0.5"->0.5 · "1.234.567"->1234567 · ""->NaN
export function parseDecimalInput(raw: string): number {
  const s = raw.trim();
  if (s === "") return NaN;
  if (s.includes(",")) {
    // pt-BR: ponto = milhar, vírgula = decimal
    return Number(s.replace(/\./g, "").replace(",", "."));
  }
  // sem vírgula: 1 ponto = decimal (en); 2+ pontos = milhar pt-BR
  const dots = (s.match(/\./g) ?? []).length;
  return dots > 1 ? Number(s.replace(/\./g, "")) : Number(s);
}
