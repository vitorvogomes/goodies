// Cartão KPI (DESIGN.md › kpi-card, Story 4.1): rótulo, valor completo, linha de apoio (variação ou
// nota) e Carimbo de data. Só fica colorido quando o sinal é o próprio dado (resultados), sempre
// com sinal e seta. O clique leva ao detalhe.
import Link from "next/link";
import type { ReactNode } from "react";

import { DateStamp } from "@/components/data/DateStamp";
import { cn } from "@/lib/utils";
import type { Valued } from "@/types/overview";

const UNAVAILABLE: Record<string, string> = {
  antes_do_primeiro_fechamento: "Disponível depois do fechamento do mês.",
  nao_definido: "Sem transações no mês.",
  sem_preco: "Sem preço para calcular.",
  sem_receita: "Sem receita no mês.",
};

export function KpiCard({
  label,
  valued,
  format,
  signed = false,
  suffix,
  support,
  href,
}: {
  label: string;
  valued: Valued;
  format: (value: number) => string;
  signed?: boolean;
  suffix?: string;
  support?: ReactNode;
  href?: string;
}) {
  const v = valued.value;
  const tone = signed && v !== null ? (v > 0 ? "text-positive" : v < 0 ? "text-negative" : "") : "";
  const arrow = signed && v !== null && v !== 0 ? (v > 0 ? "▲ " : "▼ ") : "";
  const body = (
    <>
      <p className="type-label text-muted-foreground">{label}</p>
      {v === null ? (
        <p className="type-body text-muted-foreground">
          {UNAVAILABLE[valued.unavailable_reason ?? ""] ?? "Sem dado."}
        </p>
      ) : (
        <p className={cn("type-num-display", tone)}>
          {arrow}
          {format(v)}
          {suffix && <span className="type-caption text-muted-foreground"> {suffix}</span>}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="type-body-sm text-muted-foreground">{support}</span>
        <DateStamp asOf={valued.as_of} source={valued.source} stale={valued.stale} />
      </div>
    </>
  );
  const box = "block space-y-1.5 rounded-lg border border-border bg-card p-card-padding";
  return href ? (
    <Link href={href} className={cn(box, "hover:bg-row-highlight focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none")}>
      {body}
    </Link>
  ) : (
    <div className={box}>{body}</div>
  );
}

export function KpiSkeleton() {
  return (
    <div className="space-y-2 rounded-lg border border-border bg-card p-card-padding" aria-hidden>
      <div className="h-3 w-24 animate-pulse rounded bg-muted" />
      <div className="h-8 w-40 animate-pulse rounded bg-muted" />
      <div className="h-3 w-32 animate-pulse rounded bg-muted" />
    </div>
  );
}
