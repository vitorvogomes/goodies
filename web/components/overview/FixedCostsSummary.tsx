"use client";

// Resumo de custos fixos (Story 6.3 — DESIGN › fixed-costs-summary, EXPERIENCE › Resumo de custos
// fixos): "pago R$ x de R$ y"; só atrasados, vencendo e pendentes, nessa ordem, com data e Selo; os
// pagos recolhidos em "{n} pagos", que abre com o valor pago e a diferença do previsto (v2.2); rodapé "{n} a pagar · R$ valor" com o Carimbo de data. O clique
// leva a Caixa › Custos fixos. Números da API (AD-4).
import Link from "next/link";

import { DateStamp } from "@/components/data/DateStamp";
import { PaidDiff, paidDiffText } from "@/components/data/PaidDiff";
import { Section } from "@/components/data/Section";
import { StatusBadge } from "@/components/data/StatusBadge";
import { formatBRL, formatDate } from "@/lib/format";
import { useFixedCostMonth } from "@/lib/ledger";
import { cn } from "@/lib/utils";

export function FixedCostsSummary({ periodo }: { periodo: string }) {
  const view = useFixedCostMonth(periodo);
  const href = `/caixa/custos-fixos?periodo=${periodo}`;
  if (view.isError) {
    return (
      <section className="rounded-lg border border-border bg-card shadow-card p-card-padding type-body-sm text-negative">
        Não foi possível carregar os custos fixos.{" "}
        <button type="button" className="underline" onClick={() => view.refetch()}>
          Tentar de novo
        </button>
      </section>
    );
  }
  const data = view.data;
  if (!data) return <div className="h-40 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />;
  if (data.count === 0) return null;
  const open = data.items.filter((i) => i.status !== "pago" && i.status !== "manual");
  const paidItems = data.items.filter((i) => i.status === "pago" || i.status === "manual");
  return (
    <section aria-labelledby="custos-fixos-resumo" className="space-y-2 self-start rounded-lg border border-border bg-card shadow-card p-card-padding">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="custos-fixos-resumo" className="type-section-title">
          Custos fixos
        </h2>
        <Link href={href} className="type-body-sm text-positive underline">
          Ver custos fixos
        </Link>
      </div>
      <p className="type-body">
        pago <span className="type-num-lg">{formatBRL(data.paid_total)}</span>{" "}
        <span className="text-muted-foreground">
          de <span className="type-num-body">{formatBRL(data.total)}</span>
        </span>
      </p>
      {paidDiffText(data.difference_total) && (
        <p className={cn("type-body-sm", data.difference_total > 0 ? "text-positive" : "text-warning")}>
          {paidDiffText(data.difference_total)}
        </p>
      )}
      <ul className="divide-y divide-border type-body-sm">
        {open.map((i) => (
          <li key={i.id} className="flex min-h-11 items-center justify-between gap-2 py-1.5">
            <span className="min-w-0">
              <span className="block truncate">{i.name}</span>
              <span className="type-caption text-muted-foreground">vence {formatDate(i.due_date)}</span>
            </span>
            <span className="flex items-center gap-2">
              <span className="type-num-table">{formatBRL(i.amount)}</span>
              <StatusBadge tone={i.status === "pendente" ? "neutral" : "warning"}>{i.status}</StatusBadge>
            </span>
          </li>
        ))}
      </ul>
      {paidItems.length > 0 && (
        <Section
          bare
          headingLevel={3}
          title={`${paidItems.length} ${paidItems.length === 1 ? "pago" : "pagos"}`}
          summary={formatBRL(data.paid_total)}
          className="border-t border-border"
        >
          <ul className="divide-y divide-border type-body-sm">
            {paidItems.map((i) => (
              <li key={i.id} className="flex min-h-11 items-center justify-between gap-2 py-1.5">
                <span className="min-w-0">
                  <span className="block truncate">{i.name}</span>
                  <span className="type-caption text-muted-foreground">
                    {i.transaction ? `pago ${formatDate(i.transaction.date)}` : "marcado pago"}
                  </span>
                </span>
                <span className="flex flex-col items-end gap-0.5">
                  <span className="type-num-table">{formatBRL(i.paid_amount ?? i.amount)}</span>
                  <PaidDiff difference={i.difference} />
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2">
        <span className="type-body-sm">
          {open.length} a pagar · <span className="type-num-body">{formatBRL(data.pending_total)}</span>
        </span>
        <DateStamp asOf={data.as_of} source="ledger" />
      </div>
    </section>
  );
}
