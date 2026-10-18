"use client";

// Crescimento do patrimônio (Story 9.2 — FR-22, FR-34): crescimento = aporte + resultado no
// período, a rentabilidade por classe e por ativo e o ativo de melhor desempenho em destaque. Sem o
// início coberto: "Disponível a partir do primeiro mês fechado na v2." (ou "patrimônio não
// coberto"). Tudo da API (AD-4).
import { Button } from "@/components/ui/button";
import { useGrowth } from "@/lib/closing";
import { formatBRL, formatPercent, formatSignedBRL } from "@/lib/format";

const REASONS = {
  antes_do_primeiro_fechamento: "Disponível a partir do primeiro mês fechado na v2.",
  patrimonio_nao_coberto: "patrimônio não coberto",
} as const;

export function GrowthBlock({ periodo, leitura }: { periodo: string; leitura: string }) {
  const growth = useGrowth(periodo, leitura);
  if (growth.isError && !growth.data) {
    return (
      <div role="alert" className="flex items-center gap-2 type-body text-negative">
        Não foi possível carregar o crescimento do patrimônio.
        <Button size="sm" variant="secondary" onClick={() => growth.refetch()}>
          Tentar de novo
        </Button>
      </div>
    );
  }
  const data = growth.data;
  if (!data) return <div className="h-48 animate-pulse rounded-lg border border-border bg-card" aria-hidden />;
  return (
    <section aria-labelledby="crescimento" className="space-y-3 rounded-lg border border-border bg-card p-card-padding">
      <h2 id="crescimento" className="type-section-title">
        Crescimento do patrimônio
      </h2>
      {!data.available || data.crescimento === null ? (
        <p className="type-body text-muted-foreground">{REASONS[data.reason ?? "antes_do_primeiro_fechamento"]}</p>
      ) : (
        <>
          <p className="type-body">
            Crescimento <span className="type-num-body">{formatSignedBRL(data.crescimento)}</span> = aporte{" "}
            <span className="type-num-body">{formatBRL(data.aporte ?? 0)}</span> + resultado{" "}
            <span className="type-num-body">{formatSignedBRL(data.resultado ?? 0)}</span>
            <span className="block type-caption text-muted-foreground">
              de {formatBRL(data.start_value ?? 0)} para {formatBRL(data.end_value ?? 0)} investidos
            </span>
          </p>
          {data.best && (
            <p className="rounded-md bg-positive-tint px-3 py-2 type-body-sm text-positive">
              Melhor desempenho: <span className="font-semibold">{data.best.symbol}</span> ·{" "}
              {data.best.xirr_mensal !== null ? `${formatPercent(data.best.xirr_mensal)} a.m.` : "—"}
            </p>
          )}
          <div className="grid gap-card-gap lg:grid-cols-2">
            <table className="w-full type-body-sm">
              <caption className="pb-1 text-left type-label">Por classe</caption>
              <thead className="text-muted-foreground">
                <tr>
                  <th scope="col" className="py-1 text-left font-medium">Classe</th>
                  <th scope="col" className="py-1 text-right font-medium">Rentabilidade (a.a.)</th>
                  <th scope="col" className="py-1 text-right font-medium">Resultado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.classes.map((c) => (
                  <tr key={c.key}>
                    <th scope="row" className="py-1 text-left font-normal">{c.label}</th>
                    <td className="py-1 text-right type-num-table">
                      {c.xirr_nominal.value !== null ? formatPercent(c.xirr_nominal.value) : "—"}
                    </td>
                    <td className="py-1 text-right type-num-table">{c.resultado !== null ? formatSignedBRL(c.resultado) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table className="w-full type-body-sm">
              <caption className="pb-1 text-left type-label">Por ativo (do melhor para o pior)</caption>
              <thead className="text-muted-foreground">
                <tr>
                  <th scope="col" className="py-1 text-left font-medium">Ativo</th>
                  <th scope="col" className="py-1 text-right font-medium">Rentabilidade (a.m.)</th>
                  <th scope="col" className="py-1 text-right font-medium">Resultado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.assets.slice(0, 10).map((a) => (
                  <tr key={a.symbol} className={a.symbol === data.best?.symbol ? "font-semibold" : undefined}>
                    <th scope="row" className="py-1 text-left font-normal type-num-table">{a.symbol}</th>
                    <td className="py-1 text-right type-num-table">{a.xirr_mensal !== null ? formatPercent(a.xirr_mensal) : "—"}</td>
                    <td className="py-1 text-right type-num-table">{a.resultado !== null ? formatSignedBRL(a.resultado) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
