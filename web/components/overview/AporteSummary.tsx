"use client";

// Resumo do aporte (Story 8.4; completo na 8.8 — DESIGN › contribution-summary): o planejado do mês;
// sem valor, "Defina o aporte planejado de {mês} para ver a distribuição." leva ao campo em Aportes
// com foco. O cabeçalho leva a Investimentos › Aportes. Números da API (AD-4).
import Link from "next/link";

import { formatBRL, formatMonth } from "@/lib/format";
import { useMonthBudget } from "@/lib/planning";

export function AporteSummary({ periodo }: { periodo: string }) {
  const budget = useMonthBudget(periodo);
  const href = `/investimentos/aportes?periodo=${periodo}`;
  if (budget.isError) {
    return (
      <section className="rounded-lg border border-border bg-card p-card-padding type-body-sm text-negative">
        Não foi possível carregar o aporte do mês.{" "}
        <button type="button" className="underline" onClick={() => budget.refetch()}>
          Tentar de novo
        </button>
      </section>
    );
  }
  const data = budget.data;
  if (!data) return <div className="h-40 animate-pulse rounded-lg border border-border bg-card" aria-hidden />;
  return (
    <section aria-labelledby="resumo-aporte" className="space-y-2 rounded-lg border border-border bg-card p-card-padding">
      <h2 id="resumo-aporte" className="type-section-title">
        <Link href={href} className="hover:underline">
          Resumo do aporte
        </Link>
      </h2>
      {data.aporte_definido ? (
        <p className="flex justify-between gap-4 type-body-sm">
          <span>Planejado</span>
          <span className="type-num-body">{formatBRL(data.aporte_planejado)}</span>
        </p>
      ) : (
        <Link href={`${href}&foco=aporte`} className="type-body-sm text-positive underline">
          Defina o aporte planejado de {formatMonth(periodo)} para ver a distribuição.
        </Link>
      )}
    </section>
  );
}
