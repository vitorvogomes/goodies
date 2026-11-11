"use client";

// Visão geral › Painel (Story 4.1 — FR-13): KPIs datados na grade do DESIGN.md. Desde a v2.2 abre
// com o Saldo em caixa (o saldo conferido do extrato) e o Fluxo do mês (no lugar de "disponível para
// consumo × restante"); abaixo, Resultado do mês | Patrimônio | Resultado dos investimentos |
// Rentabilidade nominal × real (o IPCA que falta é estimado pelo último publicado). Cada bloco
// carrega, falha e tenta de novo sozinho. O Assistente de recuperação (5.8) fica acima de tudo
// enquanto a base estiver incompleta; o Crescimento do patrimônio (9.2) vem logo abaixo dos KPIs; as
// Fontes ficam no fim, recolhidas.
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { useLeitura } from "@/components/data/ReadingSelector";
import { Section } from "@/components/data/Section";
import { SourcesBlock } from "@/components/ingest/SourcesBlock";
import { AlertsStrip } from "@/components/overview/AlertsStrip";
import { AporteSummary } from "@/components/overview/AporteSummary";
import { CashCard } from "@/components/overview/CashCard";
import { FixedCostsSummary } from "@/components/overview/FixedCostsSummary";
import { GrowthBlock } from "@/components/overview/GrowthBlock";
import { KpiCard, KpiSkeleton } from "@/components/overview/KpiCard";
import { MonthFlowCard } from "@/components/overview/MonthFlowCard";
import { RecoveryWizard } from "@/components/overview/RecoveryWizard";
import { Button } from "@/components/ui/button";
import { formatBRL, formatMonth, formatPercent, formatSignedBRL } from "@/lib/format";
import { useOverviewSources, usePainel } from "@/lib/overview";
import { shiftMonth } from "@/lib/period";
import { usePeriodo } from "@/lib/use-periodo";
import type { Valued } from "@/types/overview";

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
    <Section
      title="Fontes"
      summary={fontes.data ? `${fontes.data.filter((f) => f.stale).length || "nenhuma"} desatualizada${fontes.data.filter((f) => f.stale).length > 1 ? "s" : ""}` : undefined}
      className="overflow-hidden"
    >
      {fontes.isError ? (
        <p className="type-body-sm text-negative">
          Não foi possível carregar as fontes.{" "}
          <button type="button" className="underline" onClick={() => fontes.refetch()}>
            Tentar de novo
          </button>
        </p>
      ) : (
        <div className="-mx-card-padding -mb-card-padding overflow-x-auto border-t border-border">
          <SourcesBlock sources={fontes.data ?? []} loading={fontes.isLoading} onOpenSource={openHub} />
        </div>
      )}
    </Section>
  );
}

function Painel() {
  const { periodo } = usePeriodo();
  const painel = usePainel(periodo);
  const leitura = useLeitura();

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
      {/* v2.2: o saldo conferido abre a página; o fluxo do mês substitui "disponível × restante" */}
      <div className="grid gap-card-gap lg:grid-cols-5">
        <div className="lg:col-span-2">
          <CashCard periodo={periodo} />
        </div>
        <div className="lg:col-span-3">
          <MonthFlowCard periodo={periodo} />
        </div>
      </div>
      <div className="grid gap-card-gap sm:grid-cols-2 xl:grid-cols-5">
        {data ? (
          <>
            <KpiCard
              label="Resultado do mês"
              help="Receitas − gastos − investimentos do mês: quanto o saldo das contas variou no mês."
              valued={data.resultado_mes}
              format={formatSignedBRL}
              signed
              support={variation}
              href={`/caixa/transacoes?periodo=${periodo}`}
            />
            <KpiCard
              label="Patrimônio"
            help="Valor de hoje de tudo que você tem investido (B3, Tesouro, renda fixa, debêntures, cripto) + o caixa parado na corretora."
              valued={data.patrimonio}
              format={formatBRL}
              href="/investimentos/posicoes"
            />
            <KpiCard
              label="Resultado dos investimentos"
            help="Patrimônio − o que você aplicou líquido (aportes − resgates), somados os proventos: o ganho ou a perda dos investimentos desde o início."
              valued={data.resultado_investimentos}
              format={formatSignedBRL}
              signed
            />
            <KpiCard
              label="Rentabilidade nominal"
            help="XIRR desde o início: a taxa anual que iguala cada aporte, na data dele, ao valor de hoje — pondera quanto tempo cada real ficou investido."
              valued={data.rentabilidade_nominal}
              format={(v) => formatPercent(v)}
              suffix="a.a."
              support="XIRR · desde o início"
              href="/investimentos/posicoes"
            />
            <KpiCard
              label="Rentabilidade real"
            help="A rentabilidade nominal descontada a inflação (IPCA) do mesmo período: o ganho acima da inflação."
              valued={data.rentabilidade_real}
              format={(v) => formatPercent(v)}
              suffix="a.a."
              support={realSupport(data.rentabilidade_real, periodo)}
              href="/investimentos/posicoes"
            />
          </>
        ) : (
          <>
            <KpiSkeleton />
            <KpiSkeleton />
            <KpiSkeleton />
            <KpiSkeleton />
            <KpiSkeleton />
          </>
        )}
      </div>
      <GrowthBlock periodo={periodo} leitura={leitura} withSelector />
      {/* Resumo do aporte (Épico 8) | Resumo de custos fixos, metade cada (DESIGN › Layout) */}
      <div className="grid gap-card-gap lg:grid-cols-2">
        <AporteSummary periodo={periodo} />
        <FixedCostsSummary periodo={periodo} />
      </div>
      <Fontes />
    </div>
  );
}

// O IPCA sai no meio do mês seguinte: até lá o mês que falta usa o último publicado (v2.2).
function realSupport(real: Valued, periodo: string): string | undefined {
  if (real.value === null || !real.as_of) return undefined;
  const published = formatMonth(real.as_of.slice(0, 7));
  if (!real.estimated) return `descontado o IPCA até ${published}`;
  return `IPCA até ${published}; ${formatMonth(shiftMonth(periodo, -1))} estimado pelo último`;
}

export default function PainelPage() {
  return (
    <Suspense>
      <Painel />
    </Suspense>
  );
}
