"use client";

// Visão geral › Painel (Story 4.1 — FR-13): KPIs datados na grade do DESIGN.md. Resultado do mês
// (Disponível para consumo chega no Épico 6); Patrimônio | Resultado dos investimentos |
// Rentabilidade nominal × real (7.3, descontado o IPCA). Cada bloco carrega, falha e tenta de novo
// sozinho; durante a carga, Esqueleto com a geometria final. O Assistente de recuperação (5.8) fica
// acima de tudo enquanto a base estiver incompleta.
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { SourcesBlock } from "@/components/ingest/SourcesBlock";
import { AlertsStrip } from "@/components/overview/AlertsStrip";
import { AporteSummary } from "@/components/overview/AporteSummary";
import { FixedCostsSummary } from "@/components/overview/FixedCostsSummary";
import { KpiCard, KpiSkeleton } from "@/components/overview/KpiCard";
import { RecoveryWizard } from "@/components/overview/RecoveryWizard";
import { Button } from "@/components/ui/button";
import { formatBRL, formatMonth, formatPercent, formatSignedBRL } from "@/lib/format";
import { useOverviewSources, usePainel } from "@/lib/overview";
import { useMonthBudget } from "@/lib/planning";
import { usePeriodo } from "@/lib/use-periodo";

function Fontes() {
  const fontes = useOverviewSources();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const openHub = () => {
    const next = new URLSearchParams(params);
    next.set("importar", "1");
    router.push(`${pathname}?${next}`);
  };
  return (
    <section aria-labelledby="fontes" className="space-y-2">
      <h2 id="fontes" className="type-section-title">
        Fontes
      </h2>
      {fontes.isError ? (
        <p className="type-body-sm text-negative">
          Não foi possível carregar as fontes.{" "}
          <button type="button" className="underline" onClick={() => fontes.refetch()}>
            Tentar de novo
          </button>
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card shadow-card">
          <SourcesBlock sources={fontes.data ?? []} loading={fontes.isLoading} onOpenSource={openHub} />
        </div>
      )}
    </section>
  );
}

function Painel() {
  const { periodo } = usePeriodo();
  const painel = usePainel(periodo);
  const budget = useMonthBudget(periodo);

  if (painel.isError) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-lg border border-border bg-card shadow-card p-card-padding type-body">
        Não foi possível carregar os números do Painel.
        <Button size="sm" variant="secondary" onClick={() => painel.refetch()}>
          Tentar de novo
        </Button>
      </div>
    );
  }
  const data = painel.data;
  // A variação vem pronta da API (AD-4: o front não faz conta de dinheiro).
  const delta = data?.variacao_resultado_mes.value;
  const variation =
    delta !== null && delta !== undefined ? `${formatSignedBRL(delta)} vs. mês anterior` : undefined;

  return (
    <div className="space-y-section-gap">
      <RecoveryWizard />
      <AlertsStrip />
      {data && data.a_revisar > 0 && (
        <p className="type-body-sm">
          {data.a_revisar === 1 ? "1 transação a revisar." : `${data.a_revisar} transações a revisar.`}{" "}
          <Link href={`/caixa/transacoes?periodo=${periodo}&revisar=todas`} className="text-positive underline">
            Revisar
          </Link>
        </p>
      )}
      <div className="grid gap-card-gap lg:grid-cols-2">
        {data ? (
          <KpiCard
            label="Resultado do mês"
            valued={data.resultado_mes}
            format={formatSignedBRL}
            signed
            support={variation}
            href={`/caixa/transacoes?periodo=${periodo}`}
          />
        ) : (
          <KpiSkeleton />
        )}
        {budget.data ? (
          <KpiCard
            label="Disponível para consumo"
            valued={budget.data.disponivel}
            format={formatSignedBRL}
            signed
            support={
              budget.data.restante.value !== null ? `restante ${formatSignedBRL(budget.data.restante.value)}` : undefined
            }
            href={`/caixa/orcamento?periodo=${periodo}`}
          />
        ) : (
          <KpiSkeleton />
        )}
      </div>
      <div className="grid gap-card-gap md:grid-cols-2 xl:grid-cols-4">
        {data ? (
          <>
            <KpiCard
              label="Patrimônio"
              valued={data.patrimonio}
              format={formatBRL}
              href="/investimentos/posicoes"
            />
            <KpiCard
              label="Resultado dos investimentos"
              valued={data.resultado_investimentos}
              format={formatSignedBRL}
              signed
            />
            <KpiCard
              label="Rentabilidade nominal"
              valued={data.rentabilidade_nominal}
              format={(v) => formatPercent(v)}
              suffix="a.a."
              support="XIRR · desde o início"
              href="/investimentos/posicoes"
            />
            <KpiCard
              label="Rentabilidade real"
              valued={data.rentabilidade_real}
              format={(v) => formatPercent(v)}
              suffix="a.a."
              support={
                data.rentabilidade_real.as_of
                  ? `descontado o IPCA até ${formatMonth(data.rentabilidade_real.as_of.slice(0, 7))}`
                  : "descontado o IPCA"
              }
              href="/investimentos/posicoes"
            />
          </>
        ) : (
          <>
            <KpiSkeleton />
            <KpiSkeleton />
            <KpiSkeleton />
            <KpiSkeleton />
          </>
        )}
      </div>
      {/* Resumo do aporte (Épico 8) | Resumo de custos fixos, metade cada (DESIGN › Layout) */}
      <div className="grid gap-card-gap lg:grid-cols-2">
        <AporteSummary periodo={periodo} />
        <FixedCostsSummary periodo={periodo} />
      </div>
      <Fontes />
    </div>
  );
}

export default function PainelPage() {
  return (
    <Suspense>
      <Painel />
    </Suspense>
  );
}
