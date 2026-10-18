"use client";

// Distribuição do aporte (Story 8.5 — FR-29, UX-DR38, DESIGN › allocation-distribution): os
// objetivos (progresso até o alvo, "Snow Trip · R$ 350/mês para chegar em jul/2027") e as classes
// recolhidas, expansíveis para ativos, com meta, atual, desvio (p.p.), banda e sugerido — tudo de
// `POST /api/v1/planning/distribution/preview` (o front não calcula). Pisos reduzidos → a nota.
import { ChevronRightIcon } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";

import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/button";
import { formatBRL, formatMonth, formatPercent, formatPP } from "@/lib/format";
import { useDistribution } from "@/lib/planning";
import { cn } from "@/lib/utils";
import type { Distribution, DistributionGoal } from "@/types/planning";

function goalNote(g: DistributionGoal): string {
  if (g.kind === "reserva") return g.monthly > 0 ? `${formatBRL(g.monthly)}/mês até encher` : "cheia";
  if (!g.deadline || g.monthly <= 0) return "alcançado";
  return `${formatBRL(g.monthly)}/mês para chegar em ${formatMonth(g.deadline.slice(0, 7))}`;
}

function Goals({ data }: { data: Distribution }) {
  if (!data.goals.length) return null;
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full type-body-sm">
        <caption className="sr-only">Objetivos</caption>
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2 text-left font-medium">Objetivo</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Progresso</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Alvo</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Sugerido</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.goals.map((g) => (
            <tr key={g.id}>
              <th scope="row" className="px-4 py-2 text-left font-normal">
                {g.name}
                <span className="block type-caption text-muted-foreground">{goalNote(g)}</span>
              </th>
              <td className="px-4 py-2 text-right type-num-table">
                {formatPercent(g.progress)}
                <span className="block type-caption text-muted-foreground">{formatBRL(g.current)}</span>
              </td>
              <td className="px-4 py-2 text-right type-num-table">{formatBRL(g.target)}</td>
              <td className="px-4 py-2 text-right type-num-table">{formatBRL(g.sugerido)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Classes({ data }: { data: Distribution }) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (cls: string) =>
    setOpen((cur) => {
      const next = new Set(cur);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full type-body-sm">
        <caption className="sr-only">Classes e ativos</caption>
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2 text-left font-medium">Classe / ativo</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Meta</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Atual</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Desvio</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Banda</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Sugerido</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.classes.map((c) => {
            const withAssets = c.assets.some((a) => a.sugerido != null);
            return (
              <Fragment key={c.cls}>
                <tr className="font-semibold">
                  <th scope="row" className="px-4 py-2 text-left">
                    <button
                      type="button"
                      aria-expanded={open.has(c.cls)}
                      disabled={!withAssets}
                      className="inline-flex items-center gap-1 disabled:text-foreground"
                      onClick={() => toggle(c.cls)}
                    >
                      {withAssets && (
                        <ChevronRightIcon aria-hidden className={cn("size-3.5 transition-transform", open.has(c.cls) && "rotate-90")} />
                      )}
                      {c.label}
                    </button>
                  </th>
                  <td className="px-4 py-2 text-right type-num-table">{formatPercent(c.meta)}</td>
                  <td className="px-4 py-2 text-right type-num-table">{formatPercent(c.atual)}</td>
                  <td className={cn("px-4 py-2 text-right type-num-table", c.out_of_band && "text-warning")}>{formatPP(c.desvio)}</td>
                  <td className="px-4 py-2 text-right type-num-table">± {String(c.banda).replace(".", ",")} p.p.</td>
                  <td className="px-4 py-2 text-right type-num-table">
                    <span className="inline-flex items-center gap-1">
                      {c.floor_only && <StatusBadge tooltip="acima da banda: só o piso">piso</StatusBadge>}
                      {formatBRL(c.sugerido)}
                    </span>
                  </td>
                </tr>
                {open.has(c.cls) &&
                  c.assets.map((a) => (
                    <tr key={a.id} className="text-muted-foreground">
                      <th scope="row" className="py-1.5 pr-4 pl-10 text-left font-normal">
                        <span className="type-num-table">{a.label}</span>
                      </th>
                      <td className="px-4 py-1.5 text-right type-num-table">{a.meta != null ? formatPercent(a.meta) : "—"}</td>
                      <td className="px-4 py-1.5 text-right type-num-table">{formatPercent(a.atual)}</td>
                      <td colSpan={2} />
                      <td className="px-4 py-1.5 text-right type-num-table">{a.sugerido != null ? formatBRL(a.sugerido) : "—"}</td>
                    </tr>
                  ))}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function DistributionTable({ periodo, enabled }: { periodo: string; enabled: boolean }) {
  const query = useDistribution(periodo, enabled);
  if (!enabled) return null;
  if (query.isError) {
    return (
      <div role="alert" className="flex items-center gap-2 type-body text-negative">
        Não foi possível carregar a distribuição.
        <Button size="sm" variant="secondary" onClick={() => query.refetch()}>
          Tentar de novo
        </Button>
      </div>
    );
  }
  const data = query.data;
  if (!data) return <div className="h-64 animate-pulse rounded-lg border border-border bg-card" aria-hidden />;
  return (
    <section aria-labelledby="distribuicao" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="distribuicao" className="type-section-title">
          Distribuição do aporte
        </h2>
        <span className="type-caption text-muted-foreground">total = aporte planejado · {formatBRL(data.planned)}</span>
      </div>
      <Goals data={data} />
      {data.has_targets ? (
        <>
          <Classes data={data} />
          {data.floors_reduced && (
            <p className="type-body-sm text-muted-foreground">
              Os pisos somam mais do que sobra depois dos objetivos: foram reduzidos em proporção.
            </p>
          )}
        </>
      ) : (
        <p className="rounded-lg border border-border bg-card p-card-padding type-body text-muted-foreground">
          Sem metas, a distribuição do aporte não tem base. Defina as metas em{" "}
          <Link href="/ajustes/metas" className="text-positive underline">
            Ajustes › Metas
          </Link>
          .
        </p>
      )}
    </section>
  );
}
