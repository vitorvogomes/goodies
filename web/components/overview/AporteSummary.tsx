"use client";

// Resumo do aporte (Stories 8.4 e 8.8 — DESIGN › contribution-summary, UX-DR34): o planejado,
// "Realizado R$ {total} · dos quais R$ {a caminho} na corretora, ainda não aplicados", a Barra de progresso, o a caminho por
// corretora ("importe o relatório B3 a partir de dd/mm/aaaa"), "{n} classes fora da banda" → Ver
// aportes e o % realizado com o Carimbo de data. Sem planejado, "Defina o aporte planejado de
// {mês} para ver a distribuição." leva ao campo com foco. O cabeçalho leva a Aportes. Tudo da API.
import Link from "next/link";

import { DateStamp } from "@/components/data/DateStamp";
import { ProgressBar } from "@/components/data/ProgressBar";
import { formatBRL, formatDate, formatMonth, formatPercent } from "@/lib/format";
import { useAporteSummary } from "@/lib/planning";

export function AporteSummary({ periodo }: { periodo: string }) {
  const summary = useAporteSummary(periodo);
  const href = `/investimentos/aportes?periodo=${periodo}`;
  if (summary.isError && !summary.data) {
    return (
      <section className="rounded-lg border border-border bg-card shadow-card p-card-padding type-body-sm text-negative">
        Não foi possível carregar o aporte do mês.{" "}
        <button type="button" className="underline" onClick={() => summary.refetch()}>
          Tentar de novo
        </button>
      </section>
    );
  }
  const data = summary.data;
  if (!data) return <div className="h-40 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />;
  const a = data.andamento;
  return (
    <section aria-labelledby="resumo-aporte" className="space-y-2 rounded-lg border border-border bg-card shadow-card p-card-padding">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="resumo-aporte" className="type-section-title">
          <Link href={href} className="hover:underline">
            Resumo do aporte
          </Link>
        </h2>
        {data.aporte_definido && <DateStamp asOf={data.as_of} source="ledger" />}
      </div>
      {!data.aporte_definido && data.closed ? (
        <p className="type-body-sm text-muted-foreground">Aporte planejado não definido · mês fechado</p>
      ) : !data.aporte_definido ? (
        <Link href={`${href}&foco=aporte`} className="type-body-sm text-positive underline">
          Defina o aporte planejado de {formatMonth(periodo)} para ver a distribuição.
        </Link>
      ) : (
        <>
          <p className="flex justify-between gap-4 type-body-sm">
            <span>Planejado</span>
            <span className="type-num-body">{formatBRL(a.planned)}</span>
          </p>
          <p className="type-body-sm">
            Realizado <span className="type-num-body">{formatBRL(a.realizado)}</span> · dos quais{" "}
            <span className="type-num-body">{formatBRL(a.a_caminho)}</span> na corretora, ainda não aplicados
          </p>
          <ProgressBar
            label={`Realizado em ativo ${formatPercent(a.pct_em_ativo)} e na corretora, não aplicado, ${formatPercent(a.pct_a_caminho)} do planejado`}
            solid={a.pct_em_ativo}
            hatched={a.pct_a_caminho}
            legend={{ realizado: formatBRL(a.em_ativo), aCaminho: formatBRL(a.a_caminho), pendente: formatBRL(a.pendente) }}
          />
          {data.a_caminho.map((w) => (
            <p key={w.broker} className="type-caption text-muted-foreground">
              a caminho {formatBRL(w.value)} para a {w.broker}
              {w.import_from && <> · importe o relatório B3 a partir de {formatDate(w.import_from)}</>}
            </p>
          ))}
          <div className="flex flex-wrap items-center justify-between gap-2 type-body-sm">
            {data.fora_da_banda > 0 ? (
              <Link href={href} className="text-warning underline">
                {data.fora_da_banda} {data.fora_da_banda === 1 ? "classe fora da banda" : "classes fora da banda"} · Ver
                aportes
              </Link>
            ) : (
              <span className="text-muted-foreground">todas as classes na banda</span>
            )}
            {a.pct_realizado != null && <span className="type-num-body">{formatPercent(a.pct_realizado)} realizado</span>}
          </div>
        </>
      )}
    </section>
  );
}
