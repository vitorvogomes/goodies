"use client";

// Fluxo do mês (v2.2 — F2): no lugar de "disponível para consumo × restante". Uma barra só, com o
// que entrou no mês (trabalho + resgates) dividido em custos fixos | aporte planejado | dívidas |
// gastos | sobra, e uma frase: "Sobram R$ x" ou "Faltam R$ x". Com falta, a barra é o que saiu e
// o traço marca onde as entradas acabaram; o trecho depois dele é o que passou. Os números e as
// larguras vêm prontos da API (AD-4); é uma barra de progresso, não um gráfico (DESIGN.md:554).
import Link from "next/link";

import { DateStamp } from "@/components/data/DateStamp";
import { KpiSkeleton } from "@/components/overview/KpiCard";
import { formatBRL } from "@/lib/format";
import { useMonthBudget } from "@/lib/planning";
import { cn } from "@/lib/utils";
import type { FlowPart } from "@/types/planning";

const SWATCH: Record<FlowPart["key"], string> = {
  custos_fixos: "bg-chart-2",
  aporte: "bg-positive",
  dividas: "bg-warning-dot",
  gastos: "bg-chart-3",
  sobra: "bg-positive-tint border border-positive",
};

const OVER = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-negative) 0 2px, transparent 2px 6px)",
};

export function MonthFlowCard({ periodo }: { periodo: string }) {
  const budget = useMonthBudget(periodo);
  const href = `/caixa/orcamento?periodo=${periodo}`;
  if (budget.isLoading) return <KpiSkeleton />;
  const b = budget.data;
  const flow = b?.fluxo;
  if (!b || !flow) {
    return (
      <section className="rounded-lg border border-border bg-card p-card-padding shadow-card type-body text-muted-foreground">
        {budget.isError ? "Não foi possível carregar o orçamento." : "Sem o fluxo deste mês."}
      </section>
    );
  }
  const short = flow.sobra < 0;
  const over = flow.limite_pct !== null && flow.limite_pct < 100;
  return (
    <section
      aria-labelledby="fluxo-mes"
      className="space-y-3 rounded-lg border border-border bg-card p-card-padding shadow-card"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="fluxo-mes" className="type-label text-muted-foreground">
          Fluxo do mês
        </h2>
        <Link href={href} className="type-body-sm text-positive underline">
          Orçamento
        </Link>
      </div>
      <p className="type-body">
        {short ? "Faltam " : flow.sobra > 0 ? "Sobram " : "Nada sobra "}
        {flow.sobra !== 0 && (
          <span className={cn("type-num-display whitespace-nowrap", short ? "text-negative" : "text-positive")}>
            {formatBRL(Math.abs(flow.sobra))}
          </span>
        )}
        <span className="block type-body-sm text-muted-foreground">
          {short
            ? "os gastos passaram do que sobrava depois dos custos fixos e do aporte"
            : "até o fim do mês, depois dos custos fixos, do aporte e dos gastos até agora"}
        </span>
      </p>
      {flow.parts.length > 0 && (
        <div className="space-y-2">
          <div
            role="img"
            aria-label={`Entradas de ${formatBRL(flow.entradas)}: ${flow.parts
              .map((p) => `${p.label} ${formatBRL(p.value)}`)
              .join(", ")}${short ? `; faltam ${formatBRL(-flow.sobra)}` : ""}.`}
            className="relative flex h-3 w-full overflow-hidden rounded-full bg-muted"
          >
            {flow.parts.map((p) => (
              <span
                key={p.key}
                className={cn("h-full border-r border-card last:border-r-0", SWATCH[p.key])}
                style={{ width: `${p.pct}%` }}
              />
            ))}
            {over && (
              <span
                aria-hidden
                className="absolute inset-y-0 right-0 border-l-2 border-negative"
                style={{ left: `${flow.limite_pct}%`, ...OVER }}
              />
            )}
          </div>
          <ul className="grid gap-x-4 gap-y-1 type-body-sm sm:grid-cols-2 xl:grid-cols-3">
            {flow.parts.map((p) => (
              <li key={p.key} className="flex items-center gap-1.5">
                <span aria-hidden className={cn("size-2.5 shrink-0 rounded-sm", SWATCH[p.key])} />
                <span className="truncate text-muted-foreground">{p.label}</span>
                <span className="ml-auto type-num-table">{formatBRL(p.value)}</span>
              </li>
            ))}
          </ul>
          <p className="flex flex-wrap items-center justify-between gap-2 type-caption text-muted-foreground">
            <span>
              entrou <span className="type-num-table text-foreground">{formatBRL(flow.entradas)}</span> (trabalho +
              resgates)
            </span>
            <DateStamp asOf={b.as_of} source="ledger" />
          </p>
        </div>
      )}
    </section>
  );
}
