// Formatadores pt-BR (Story 1.8 — UX-DR24, EXPERIENCE › Números e formatação financeira).
// Só formatam: nenhuma conta de dinheiro aqui (AD-4). Moeda completa (nunca mil/k/MM), espaço não
// separável após "R$", menos tipográfico (−), percentual com 2 casas, desvio em p.p.

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const USD = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

const MINUS = "\u2212";
const NBSP = "\u00a0";

// Zero na precisão exibida (2 casas) nunca leva sinal: −0, −0,004 ou ruído de float (−1e-12).
function isDisplayZero(value: number): boolean {
  return Math.abs(value) < 0.005;
}

// O hífen do Intl vira o menos tipográfico.
function typographic(text: string, value: number): string {
  if (isDisplayZero(value)) return text.replace(/^-/, "");
  return text.replace(/^-/, MINUS);
}

function decimal2(value: number): string {
  return Math.abs(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function sign(value: number, explicitPlus: boolean): string {
  if (isDisplayZero(value)) return "";
  if (value < 0) return MINUS;
  return explicitPlus ? "+" : "";
}

export function formatBRL(value: number): string {
  return typographic(BRL.format(isDisplayZero(value) ? 0 : value), value);
}

// Variação e resultado: sinal explícito dos dois lados ("+R$ 682,10" / "−R$ 163,80").
export function formatSignedBRL(value: number): string {
  return !isDisplayZero(value) && value > 0 ? `+${formatBRL(value)}` : formatBRL(value);
}

// Valor em dólar no padrão pt-BR (ex.: 1234.56 -> "US$ 1.234,56"): cripto mostra R$ e US$ (v2.2).
export function formatUSD(value: number): string {
  return typographic(USD.format(isDisplayZero(value) ? 0 : value), value);
}

// Percentual já em % (Pct da API), 2 casas e sufixo de período opcional: "10,90% a.a.".
export function formatPercent(value: number, period?: "a.a." | "a.m."): string {
  return `${sign(value, false)}${decimal2(value)}%${period ? ` ${period}` : ""}`;
}

// Taxa decimal -> percentual com 2 casas (ex: 0.0853 -> "8,53%"). null -> "—".
export function formatRate(value: number | null): string {
  if (value == null) return "—";
  return formatPercent(value * 100);
}

// Desvio em pontos percentuais, com sinal e sem seta: "−3,60 p.p." / "+8,70 p.p.".
export function formatPP(value: number): string {
  return `${sign(value, true)}${decimal2(value)}${NBSP}p.p.`;
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

// ISO -> "dd/mm/aaaa hh:mm" (pt-BR, horário de Brasília). null/inválido -> "—".
export function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" });
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

// Valor digitado (pt-BR ou en) → string decimal com 2 casas para a API, sem passar por float (AD-4).
// "1.234,56" → "1234.56" · "42,9" → "42.90" · "-10" → "-10.00" · inválido/vazio → null.
export function normalizeMoneyInput(raw: string): string | null {
  const s = raw.replace(/\s|R\$| /g, "").replace("−", "-");
  if (!s) return null;
  const parts = decimalParts(s, 2);
  return parts && `${parts.sign}${parts.int}.${parts.frac.padEnd(2, "0")}`;
}

function decimalParts(s: string, maxDecimals: number): { sign: string; int: string; frac: string } | null {
  let body = s;
  if (s.includes(",")) body = s.replace(/\./g, "").replace(",", ".");
  else if ((s.match(/\./g) ?? []).length > 1) body = s.replace(/\./g, "");
  const m = new RegExp(`^([+-]?)(\\d+)(?:\\.(\\d{1,${maxDecimals}}))?$`).exec(body);
  if (!m) return null;
  return { sign: m[1] === "-" ? "-" : "", int: m[2].replace(/^0+(?=\d)/, ""), frac: m[3] ?? "" };
}

// Preço unitário (Ajustes › Preços manuais): até 8 casas, como `asset_prices.price_brl` — token de
// carteira pode valer menos de um centavo. "0,0042" → "0.0042"; mais de 8 casas → null.
export function normalizeUnitPriceInput(raw: string): string | null {
  const s = raw.replace(/\s|R\$/g, "").replace("−", "-");
  const parts = s ? decimalParts(s, 8) : null;
  if (!parts) return null;
  return parts.frac ? `${parts.sign}${parts.int}.${parts.frac}` : `${parts.sign}${parts.int}`;
}

// Decimal da API ("0.00420000") → "0,0042": sem zeros à direita, com no mínimo 2 casas. Só texto.
export function formatUnitPrice(value: string): string {
  const [int, frac = ""] = value.split(".");
  return `${int},${frac.replace(/0+$/, "").padEnd(2, "0")}`;
}
