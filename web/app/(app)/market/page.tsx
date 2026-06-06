"use client";

// STORY-03-11 — tela de preços do Market Engine com indicador de staleness.
import { Button } from "@/components/ui";
import { formatBRL } from "@/lib/format";
import { usePrices } from "@/lib/market";
import type { Price } from "@/types/market";

function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

// 4 estados visualmente distintos sobre 3 conceitos: não encontrado | manual | via API.
function StatusBadge({ p }: { p: Price }) {
  const base = "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs";
  if (p.price_brl == null) {
    return <span className={`${base} bg-loss/15 text-loss`}>✕ não encontrado</span>;
  }
  if (p.is_manual) {
    return <span className={`${base} bg-accent/15 text-accent`}>✎ manual</span>;
  }
  if (p.stale) {
    return <span className={`${base} bg-warning/15 text-warning`}>⟳ via API · desatualizado</span>;
  }
  return <span className={`${base} bg-gain/15 text-gain`}>↻ via API</span>;
}

function Legend() {
  const item = (cls: string, label: string) => (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${cls}`} />
      {label}
    </span>
  );
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-foreground/50">
      {item("bg-gain", "via API (atual)")}
      {item("bg-warning", "via API (desatualizado)")}
      {item("bg-accent", "manual (você definiu)")}
      {item("bg-loss", "não encontrado")}
    </div>
  );
}

export default function MarketPricesPage() {
  const { data, isLoading, isError } = usePrices();
  const prices = data?.prices ?? [];
  const staleCount = prices.filter((p) => p.stale || p.price_brl == null).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-mono text-2xl font-semibold text-foreground">Preços</h1>
        <a href="/portfolio/positions">
          <Button variant="ghost">Posições</Button>
        </a>
      </div>

      {prices.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-2">
          <Legend />
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-foreground/50">
            <span>
              Ativos <span className="tabular-nums text-foreground/70">{prices.length}</span>
            </span>
            <span>
              Sem preço/desatualizados{" "}
              <span
                className={`tabular-nums ${staleCount > 0 ? "text-warning" : "text-foreground/70"}`}
              >
                {staleCount}
              </span>
            </span>
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-foreground/60">
            <tr>
              <th className="px-4 py-2.5 font-medium">Ativo</th>
              <th className="px-4 py-2.5 font-medium">Fonte</th>
              <th className="px-4 py-2.5 text-right font-medium">Preço (BRL)</th>
              <th className="px-4 py-2.5 text-right font-medium">USD</th>
              <th className="px-4 py-2.5 text-right font-medium">Atualizado</th>
              <th className="px-4 py-2.5 text-right font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-foreground/50">
                  Carregando…
                </td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-loss">
                  Erro ao carregar preços.
                </td>
              </tr>
            )}
            {!isLoading && !isError && prices.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-foreground/50">
                  Nenhum ativo na carteira.
                </td>
              </tr>
            )}
            {!isLoading &&
              !isError &&
              prices.map((p) => (
                <tr key={p.ticker} className="border-t border-border">
                  <td className="px-4 py-2.5 font-medium text-foreground/90">{p.ticker}</td>
                  <td className="px-4 py-2.5 text-foreground/60">{p.source ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                    {p.price_brl != null ? formatBRL(p.price_brl) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-foreground/50">
                    {p.price_usd != null ? p.price_usd.toFixed(2) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right text-xs text-foreground/50">
                    {fmtWhen(p.last_updated)}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <StatusBadge p={p} />
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
