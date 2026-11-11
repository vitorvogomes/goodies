"use client";

// Caixa › Orçamento (Story 6.6 — FR-15, FR-16, FR-17, UX-DR36): a Conta do orçamento e, ao lado, o
// Consumido por grupo, com a pizza dos gastos por grupo em cima (v2.2). Tudo da rota de orçamento
// de `closing` (mês fechado = congelado).
import { BudgetLedger } from "@/components/caixa/BudgetLedger";
import { ConsumedByGroup } from "@/components/caixa/ConsumedByGroup";
import { PieBreakdown } from "@/components/charts/PieBreakdown";
import { DateStamp } from "@/components/data/DateStamp";
import { Button } from "@/components/ui/button";
import { formatBRL, formatMonth } from "@/lib/format";
import { useMonthBudget } from "@/lib/planning";
import { usePeriodo } from "@/lib/use-periodo";

export default function OrcamentoPage() {
  const { periodo } = usePeriodo();
  const budget = useMonthBudget(periodo);
  if (budget.isError) {
    return (
      <div role="alert" className="flex items-center gap-2 type-body text-negative">
        Não foi possível carregar o orçamento.
        <Button size="sm" variant="secondary" onClick={() => budget.refetch()}>
          Tentar de novo
        </Button>
      </div>
    );
  }
  const data = budget.data;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="type-section-title">Orçamento de {formatMonth(periodo)}</h2>
        {data && <DateStamp asOf={data.as_of} source={data.source === "snapshot" ? "fechamento" : "ledger"} />}
      </div>
      {!data ? (
        <div className="h-96 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />
      ) : (
        <div className="grid gap-card-gap lg:grid-cols-2">
          {/* min-w-0: no celular a grade de 1 coluna não pode crescer com as tabelas (v2.2) */}
          <div className="min-w-0 rounded-lg border border-border bg-card shadow-card p-card-padding">
            <BudgetLedger budget={data} periodo={periodo} />
          </div>
          <div className="min-w-0 space-y-card-gap">
            <PieBreakdown
              id="pizza-gastos-mes"
              title="Para onde foram os gastos"
              slices={data.consumido_por_grupo
                .filter((g) => g.value > 0)
                .map((g) => ({ key: g.group, label: g.group, value: g.value, pct: g.pct }))}
              center={{ label: "gastos do mês", value: formatBRL(data.grupos_total) }}
              empty="Nenhum gasto no mês."
            />
            <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-card p-card-padding">
              <ConsumedByGroup budget={data} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
