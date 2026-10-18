"use client";

// Consumido por grupo (Story 6.6 — EXPERIENCE › Caixa › Orçamento): grupo → subcategoria com o % do
// consumido (sem os custos fixos casados nem as dívidas); rodapé com os gastos brutos e as deduções.
// Percentuais e totais vêm da API.
import { ChevronRightIcon } from "lucide-react";
import { Fragment, useState } from "react";

import { formatBRL, formatPercent } from "@/lib/format";
import type { MonthBudget } from "@/types/planning";

export function ConsumedByGroup({ budget }: { budget: MonthBudget }) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (g: string) =>
    setOpen((s) => {
      const next = new Set(s);
      if (next.has(g)) next.delete(g);
      else next.add(g);
      return next;
    });
  const total = budget.consumido_por_grupo.reduce((n, g) => n + g.count, 0);
  return (
    <section aria-labelledby="consumido-grupo" className="space-y-2 self-start">
      <h2 id="consumido-grupo" className="type-section-title">
        Consumido por grupo <span className="type-body-sm font-normal text-muted-foreground">sem os custos fixos</span>
      </h2>
      <table className="w-full type-body-sm">
        <caption className="sr-only">Consumido por grupo e subcategoria</caption>
        <thead className="text-muted-foreground">
          <tr>
            <th scope="col" className="py-1 text-left font-normal">Grupo</th>
            <th scope="col" className="py-1 text-right font-normal">Gasto</th>
            <th scope="col" className="py-1 text-right font-normal">% do consumido</th>
            <th scope="col" className="py-1 text-right font-normal">Transações</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {budget.consumido_por_grupo.length === 0 && (
            <tr>
              <td colSpan={4} className="py-2 text-muted-foreground">
                Nenhum consumo no mês.
              </td>
            </tr>
          )}
          {budget.consumido_por_grupo.map((g) => (
            <Fragment key={g.group}>
              <tr>
                <th scope="row" className="py-1.5 text-left font-normal">
                  <button
                    type="button"
                    aria-expanded={open.has(g.group)}
                    className="inline-flex items-center gap-1"
                    onClick={() => toggle(g.group)}
                  >
                    <ChevronRightIcon
                      aria-hidden
                      className={`size-3.5 transition-transform ${open.has(g.group) ? "rotate-90" : ""}`}
                    />
                    {g.group}
                  </button>
                </th>
                <td className="py-1.5 text-right type-num-table">{formatBRL(g.value)}</td>
                <td className="py-1.5 text-right type-num-table">{formatPercent(g.pct)}</td>
                <td className="py-1.5 text-right type-num-table">{g.count}</td>
              </tr>
              {open.has(g.group) &&
                g.subcategories.map((s) => (
                  <tr key={`${g.group}-${s.name}`} className="text-muted-foreground">
                    <th scope="row" className="py-1 pl-6 text-left font-normal">
                      {s.name}
                    </th>
                    <td className="py-1 text-right type-num-table">{formatBRL(s.value)}</td>
                    <td className="py-1 text-right type-num-table">{formatPercent(s.pct)}</td>
                    <td className="py-1 text-right type-num-table">{s.count}</td>
                  </tr>
                ))}
            </Fragment>
          ))}
        </tbody>
        <tfoot className="border-t border-foreground">
          <tr>
            <th scope="row" className="py-1.5 text-left font-semibold">
              Consumido
            </th>
            <td className="py-1.5 text-right type-num-table font-semibold">
              {budget.consumido.value === null ? "—" : formatBRL(budget.consumido.value)}
            </td>
            <td className="py-1.5 text-right type-num-table">{budget.consumido_por_grupo.length ? "100,00%" : "—"}</td>
            <td className="py-1.5 text-right type-num-table">{total}</td>
          </tr>
          <tr className="text-muted-foreground">
            <th scope="row" className="py-1 text-left font-normal">
              Gastos brutos do mês
            </th>
            <td className="py-1 text-right type-num-table">{formatBRL(budget.gastos)}</td>
            <td colSpan={2} />
          </tr>
          <tr className="text-muted-foreground">
            <th scope="row" className="py-1 text-left font-normal">
              − Devoluções
            </th>
            <td className="py-1 text-right type-num-table">{formatBRL(budget.devolucoes)}</td>
            <td colSpan={2} />
          </tr>
        </tfoot>
      </table>
    </section>
  );
}
