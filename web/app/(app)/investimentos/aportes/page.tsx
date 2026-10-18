"use client";

// Investimentos › Aportes (Story 8.4 — FR-28): o aporte planejado do mês e o disponível depois dele.
// A Distribuição do aporte (8.5–8.7) vem abaixo. `?foco=aporte` (Painel, aviso) abre com o campo
// em foco.
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { AportePlanejado } from "@/components/investimentos/AportePlanejado";
import { DistributionTable } from "@/components/investimentos/DistributionTable";
import { Button } from "@/components/ui/button";
import { useMonthBudget, useSetAporte } from "@/lib/planning";
import { usePeriodo } from "@/lib/use-periodo";

function Aportes() {
  const { periodo } = usePeriodo();
  const params = useSearchParams();
  const budget = useMonthBudget(periodo);
  const setAporte = useSetAporte();
  if (budget.isError) {
    return (
      <div role="alert" className="flex items-center gap-2 type-body text-negative">
        Não foi possível carregar o aporte do mês.
        <Button size="sm" variant="secondary" onClick={() => budget.refetch()}>
          Tentar de novo
        </Button>
      </div>
    );
  }
  if (!budget.data) return <div className="h-40 animate-pulse rounded-lg border border-border bg-card" aria-hidden />;
  const data = budget.data;
  return (
    <div className="space-y-section-gap">
      <AportePlanejado
        key={`${periodo}-${data.aporte_definido}-${data.aporte_planejado}`}
        budget={data}
        periodo={periodo}
        saving={setAporte.isPending}
        autoFocus={params.get("foco") === "aporte"}
        onCommit={(valor, onError) => setAporte.mutate({ periodo, valor }, { onError })}
      />
      <DistributionTable periodo={periodo} enabled={data.aporte_definido} readOnly={data.closed} />
    </div>
  );
}

export default function AportesPage() {
  return (
    <Suspense>
      <Aportes />
    </Suspense>
  );
}
