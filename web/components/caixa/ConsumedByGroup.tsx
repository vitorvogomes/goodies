"use client";

// Consumido por grupo (Story 6.6 — EXPERIENCE › Caixa › Orçamento): grupo → subcategoria com o % do
// consumido (sem os custos fixos casados nem as dívidas); rodapé com os gastos brutos e as deduções.
// Percentuais e totais vêm da API; abaixo, o rodapé do orçamento (6.7). Pedido de 18/10/2026: todos
// os grupos de gasto, com os custos fixos pagos de cada um ao lado, e o investimento do mês por
// categoria — que aparece na análise do mês, mas não é custo.
import { ChevronRightIcon } from "lucide-react";
import { Fragment, useState } from "react";

import { formatBRL, formatPercent } from "@/lib/format";
import type { MonthBudget } from "@/types/planning";

// Rodapé do orçamento (Story 6.7 — FR-20): custos fixos pagos, gastos do mês, investimento (fora
// dos gastos), taxa de poupança ((trabalho − (gastos − devoluções)) / trabalho) e investimento do
// mês ÷ receita do trabalho — o "realizado total" do Épico 8. Sem receita: "sem receita do trabalho".
function BudgetFooter({ budget }: { budget: MonthBudget }) {
  const pct = (v: MonthBudget["taxa_poupanca"]) =>
    v.value === null ? "— sem receita do trabalho" : formatPercent(v.value);
  const rows: [string, string][] = [
    ["Custos fixos pagos (fora do consumido)", formatBRL(budget.custos_fixos_pagos)],
    ["Gastos do mês", formatBRL(budget.gastos)],
    ["Investimento (realizado total, fora dos gastos)", formatBRL(budget.investido)],
    ["Taxa de poupança", pct(budget.taxa_poupanca)],
    ["Aporte ÷ receita do trabalho", pct(budget.aporte_sobre_trabalho)],
  ];
  return (
    <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 border-t border-border pt-3 type-body-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="text-right type-num-table">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

// O investimento do mês por categoria: entra na análise do mês, mas não é custo (fora do consumido
// e dos gastos).
function Investments({ budget }: { budget: MonthBudget }) {
  if (budget.investido_por_categoria.length === 0) return null;
  return (
    <table className="w-full type-body-sm">
      <caption className="pb-1 text-left type-body-sm font-semibold">
        Investimentos do mês <span className="font-normal text-muted-foreground">não é custo: fora do consumido</span>
      </caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">Categoria</th>
          <th scope="col">Valor</th>
          <th scope="col">% do investido</th>
          <th scope="col">Transações</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {budget.investido_por_categoria.map((i) => (
          <tr key={i.name}>
            <th scope="row" className="py-1 pl-[18px] text-left font-normal">{i.name}</th>
            <td className="py-1 text-right type-num-table">{formatBRL(i.value)}</td>
            <td className="py-1 text-right type-num-table">{formatPercent(i.pct)}</td>
            <td className="py-1 pl-3 text-right type-num-table">{i.count}</td>
          </tr>
        ))}
      </tbody>
      <tfoot className="border-t border-foreground">
        <tr>
          <th scope="row" className="py-1.5 text-left font-normal">Investido no mês</th>
          <td className="py-1.5 text-right type-num-table">{formatBRL(budget.investido)}</td>
          <td colSpan={2} />
        </tr>
      </tfoot>
    </table>
  );
}

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
  if (!budget.detalhe) {
    return (
      <p className="type-body-sm text-muted-foreground">
        O consumido por grupo não existia quando este mês foi fechado.
      </p>
    );
  }
  return (
    <section aria-labelledby="consumido-grupo" className="space-y-2 self-start">
      <h2 id="consumido-grupo" className="type-section-title">
        Consumido por grupo{" "}
        <span className="type-body-sm font-normal text-muted-foreground">custos fixos ao lado, fora do consumido</span>
      </h2>
      <table className="w-full type-body-sm">
        <caption className="sr-only">Consumido por grupo e subcategoria</caption>
        <thead className="text-muted-foreground">
          <tr>
            <th scope="col" className="py-1 text-left font-normal">Grupo</th>
            <th scope="col" className="py-1 text-right font-normal">Consumido</th>
            <th scope="col" className="py-1 text-right font-normal">% do consumido</th>
            <th scope="col" className="py-1 text-right font-normal">Custos fixos</th>
            <th scope="col" className="py-1 text-right font-normal">Transações</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {budget.consumido_por_grupo.length === 0 && (
            <tr>
              <td colSpan={5} className="py-2 text-muted-foreground">
                Nenhum consumo no mês.
              </td>
            </tr>
          )}
          {budget.consumido_por_grupo.map((g) => (
            <Fragment key={g.group}>
              <tr className={g.value === 0 && g.fixos === 0 ? "text-muted-foreground" : undefined}>
                <th scope="row" className="py-1.5 text-left font-normal">
                  {g.subcategories.length > 0 ? (
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
                  ) : (
                    <span className="pl-[18px]">{g.group}</span>
                  )}
                </th>
                <td className="py-1.5 text-right type-num-table">{formatBRL(g.value)}</td>
                <td className="py-1.5 text-right type-num-table">{formatPercent(g.pct)}</td>
                <td className="py-1.5 text-right type-num-table text-muted-foreground">
                  {g.fixos > 0 ? formatBRL(g.fixos) : "—"}
                </td>
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
                    <td />
                    <td className="py-1 text-right type-num-table">{s.count}</td>
                  </tr>
                ))}
            </Fragment>
          ))}
        </tbody>
        <tfoot className="border-t border-foreground">
          <tr>
            <th scope="row" className="py-1.5 text-left font-normal">
              Total dos grupos
            </th>
            <td className="py-1.5 text-right type-num-table">{formatBRL(budget.grupos_total)}</td>
            <td className="py-1.5 text-right type-num-table">{budget.grupos_total > 0 ? "100,00%" : "—"}</td>
            <td className="py-1.5 text-right type-num-table text-muted-foreground">{formatBRL(budget.deducao_fixos)}</td>
            <td className="py-1.5 text-right type-num-table">{total}</td>
          </tr>
          <tr className="text-muted-foreground">
            <th scope="row" className="py-1 text-left font-normal">
              − Devoluções
            </th>
            <td className="py-1 text-right type-num-table">{formatBRL(budget.devolucoes)}</td>
            <td colSpan={3} />
          </tr>
          <tr>
            <th scope="row" className="py-1.5 text-left font-semibold">
              = Consumido
            </th>
            <td className="py-1.5 text-right type-num-table font-semibold">
              {budget.consumido.value === null ? "—" : formatBRL(budget.consumido.value)}
            </td>
            <td colSpan={3} />
          </tr>
          <tr className="text-muted-foreground">
            <th scope="row" className="py-1 text-left font-normal">
              Gastos brutos do mês
            </th>
            <td className="py-1 text-right type-num-table">{formatBRL(budget.gastos)}</td>
            <td colSpan={3} />
          </tr>
        </tfoot>
      </table>
      <Investments budget={budget} />
      <BudgetFooter budget={budget} />
    </section>
  );
}
