"use client";

// Crescimento do patrimônio (Story 9.2 — FR-22, FR-34): crescimento = aporte + resultado no
// período, a rentabilidade por classe e por ativo e o ativo de melhor desempenho em destaque. Sem o
// início coberto: "Disponível a partir do primeiro mês fechado na v2." (ou "patrimônio não
// coberto"). Tudo da API (AD-4). A conta em blocos (início + aporte +
// resultado = fim), melhor e pior desempenho lado a lado e a rentabilidade das classes e dos ativos
// na mesma unidade (% a.m.; o % a.a. da classe fica de apoio). O bloco cripto entra como um todo —
// quanto saiu × quanto vale, com o XIRR dos fluxos do ledger; sem o preço das carteiras no início do
// período, desde o 1º aporte (marcado). No Painel, com o Seletor de leitura no cabeçalho.
import type { ReactNode } from "react";

import { MoneyDual } from "@/components/data/MoneyDual";
import { ReadingSelector } from "@/components/data/ReadingSelector";
import { TrendArrow } from "@/components/data/TrendArrow";
import { Button } from "@/components/ui/button";
import { useGrowth } from "@/lib/closing";
import { formatBRL, formatPercent, formatSignedBRL, formatUSD } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { GrowthAsset } from "@/types/closing";

const REASONS = {
  antes_do_primeiro_fechamento: "Disponível a partir do primeiro mês fechado na v2.",
  patrimonio_nao_coberto: "patrimônio não coberto",
} as const;

function Signed({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground">—</span>;
  return (
    <span className={cn("whitespace-nowrap", value > 0 && "text-positive", value < 0 && "text-negative")}>
      {value !== 0 && <TrendArrow up={value > 0} />}
      {formatSignedBRL(value)}
    </span>
  );
}

function Term({ label, children, op }: { label: string; children: ReactNode; op?: string }) {
  return (
    <div className="flex items-center gap-3">
      {op && (
        <span aria-hidden className="type-num-body text-muted-foreground">
          {op}
        </span>
      )}
      <div className="space-y-0.5">
        <p className="type-caption text-muted-foreground">{label}</p>
        <p className="type-num-body">{children}</p>
      </div>
    </div>
  );
}

function Highlight({ title, asset, good }: { title: string; asset: GrowthAsset; good: boolean }) {
  return (
    <div className={cn("min-w-60 flex-1 rounded-md px-3 py-2 type-body-sm", good ? "bg-positive-tint" : "bg-muted")}>
      <p className="type-caption text-muted-foreground">{title}</p>
      <p>
        <span className="font-semibold type-num-table">{asset.symbol}</span>{" "}
        <span className={good ? "text-positive" : "text-negative"}>
          {asset.xirr_mensal !== null ? `${formatPercent(asset.xirr_mensal)} a.m.` : "—"}
        </span>
        <span className="text-muted-foreground"> · </span>
        <Signed value={asset.resultado} />
      </p>
    </div>
  );
}

export function GrowthBlock({
  periodo,
  leitura,
  withSelector = false,
}: {
  periodo: string;
  leitura: string;
  withSelector?: boolean;
}) {
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
  if (!data) return <div className="h-48 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />;
  return (
    <section aria-labelledby="crescimento" className="space-y-4 rounded-lg border border-border bg-card shadow-card p-card-padding">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="crescimento" className="type-section-title">
            Crescimento do patrimônio
          </h2>
          {withSelector && <ReadingSelector />}
        </div>
        {data.available && data.crescimento !== null && (
          <p className="type-body">
            cresceu <Signed value={data.crescimento} />
          </p>
        )}
      </div>
      {!data.available || data.crescimento === null ? (
        <p className="type-body text-muted-foreground">{REASONS[data.reason ?? "antes_do_primeiro_fechamento"]}</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-md border border-border px-4 py-3">
            <Term label="Investido no início">{formatBRL(data.start_value ?? 0)}</Term>
            <Term label="Aporte do período" op="+">
              {formatBRL(data.aporte ?? 0)}
            </Term>
            <Term label="Resultado dos investimentos" op="+">
              <Signed value={data.resultado} />
            </Term>
            <Term label="Investido no fim" op="=">
              <span className="font-semibold">{formatBRL(data.end_value ?? 0)}</span>
            </Term>
          </div>
          {(data.best || data.worst) && (
            <div className="flex flex-wrap gap-card-gap">
              {data.best && <Highlight title="Melhor desempenho" asset={data.best} good />}
              {data.worst && <Highlight title="Pior desempenho" asset={data.worst} good={false} />}
            </div>
          )}
          <div className="grid gap-card-gap lg:grid-cols-2">
            <table className="w-full type-body-sm">
              <caption className="pb-1 text-left type-label">Por classe</caption>
              <thead className="text-muted-foreground">
                <tr>
                  <th scope="col" className="py-1 text-left font-medium">Classe</th>
                  <th scope="col" className="py-1 text-right font-medium">Rentabilidade</th>
                  <th scope="col" className="py-1 text-right font-medium">Resultado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.classes.map((c) => (
                  <tr key={c.key}>
                    <th scope="row" className="py-1.5 text-left font-normal">
                      {c.label}
                      {c.saiu !== null && c.vale !== null && (
                        <span className="block type-caption text-muted-foreground">
                          saiu {formatBRL(c.saiu)} · vale {formatBRL(c.vale)}
                          {c.vale_usd != null && ` (${formatUSD(c.vale_usd)})`}
                          {c.desde_inicio && " · desde o 1º aporte"}
                        </span>
                      )}
                    </th>
                    <td className="py-1.5 text-right type-num-table">
                      {c.xirr_mensal !== null ? (
                        <span className="inline-flex flex-col items-end">
                          <span>{formatPercent(c.xirr_mensal)} a.m.</span>
                          {c.xirr_nominal.value !== null && (
                            <span className="type-caption text-muted-foreground">
                              ≈ {formatPercent(c.xirr_nominal.value)} a.a.
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="py-1.5 text-right type-num-table">
                      <MoneyDual brl={<Signed value={c.resultado} />} usd={c.resultado_usd} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table className="w-full type-body-sm">
              <caption className="pb-1 text-left type-label">Por ativo · do melhor para o pior</caption>
              <thead className="text-muted-foreground">
                <tr>
                  <th scope="col" className="py-1 text-left font-medium">Ativo</th>
                  <th scope="col" className="py-1 text-right font-medium">Rentabilidade</th>
                  <th scope="col" className="py-1 text-right font-medium">Resultado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.assets.slice(0, 10).map((a) => (
                  <tr key={a.symbol}>
                    <th scope="row" className="py-1.5 text-left font-normal type-num-table">{a.symbol}</th>
                    <td className="py-1.5 text-right type-num-table">
                      {a.xirr_mensal !== null ? `${formatPercent(a.xirr_mensal)} a.m.` : "—"}
                    </td>
                    <td className="py-1.5 text-right type-num-table">
                      <Signed value={a.resultado} />
                    </td>
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
