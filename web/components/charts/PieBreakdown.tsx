"use client";

// Pizza (v2.2 — F4): a parte de cada item no todo, uma fatia por item (sem "outros"), do maior para
// o menor, em tons do verde principal (`--color-pie-1..8`, claro e escuro alternados). Como os tons
// se repetem e se parecem, quem identifica a fatia é a legenda ao lado (embaixo no celular), com %
// e valor; passar o mouse ou tocar numa fatia ou num item da legenda destaca o par. "Ver como
// tabela" mostra os mesmos números. As fatias e os % vêm prontos da API (AD-4).
import { type ReactNode, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { Button } from "@/components/ui/button";
import { formatBRL, formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface PieSlice {
  key: string;
  label: string;
  value: number;
  pct: number;
}

export const pieColor = (i: number) => `var(--pie-${(i % 8) + 1})`;

export function PieBreakdown({
  id,
  title,
  slices,
  center,
  actions,
  onPick,
  empty = "Nada para mostrar no período.",
}: {
  id: string;
  title: string;
  slices: PieSlice[];
  /** Texto no meio da rosca (ex.: o total). */
  center?: { label: string; value: string };
  actions?: ReactNode;
  /** Clique num item (ex.: abrir as transações do grupo). */
  onPick?: (s: PieSlice) => void;
  empty?: string;
}) {
  const [picked, setActive] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  // a lista pode trocar (Classes ↔ Ativos, outro período) com uma fatia tocada: índice fora dela
  // vale "nenhuma" (review v2.2 — antes, slices[i] indefinido derrubava a página)
  const active = picked !== null && picked < slices.length ? picked : null;
  return (
    <section aria-labelledby={id} className="space-y-3 rounded-lg border border-border bg-card p-card-padding shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={id} className="type-section-title">
          {title}
        </h3>
        <div className="flex items-center gap-2">
          {actions}
          <Button size="sm" variant="ghost" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
            {asTable ? "Ver como gráfico" : "Ver como tabela"}
          </Button>
        </div>
      </div>
      {slices.length === 0 ? (
        <p className="type-body-sm text-muted-foreground">{empty}</p>
      ) : asTable ? (
        <table className="w-full type-body-sm">
          <caption className="sr-only">{title}</caption>
          <thead className="text-muted-foreground">
            <tr>
              <th scope="col" className="py-1 text-left font-medium">Item</th>
              <th scope="col" className="py-1 text-right font-medium">% do total</th>
              <th scope="col" className="py-1 text-right font-medium">Valor</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {slices.map((s) => (
              <tr key={s.key}>
                <th scope="row" className="py-1.5 text-left font-normal">{s.label}</th>
                <td className="py-1.5 text-right type-num-table">{formatPercent(s.pct)}</td>
                <td className="py-1.5 text-right type-num-table">{formatBRL(s.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="grid items-center gap-4 sm:grid-cols-[minmax(0,14rem)_1fr]">
          <div className="relative mx-auto aspect-square w-full max-w-56" aria-hidden>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="label"
                  innerRadius="58%"
                  outerRadius="98%"
                  startAngle={90}
                  endAngle={-270}
                  stroke="var(--color-card)"
                  strokeWidth={2}
                  isAnimationActive={false}
                  onMouseEnter={(_, i) => setActive(i)}
                  onMouseLeave={() => setActive(null)}
                  onClick={(_, i) => setActive((cur) => (cur === i ? null : i))}
                >
                  {slices.map((s, i) => (
                    <Cell
                      key={s.key}
                      fill={pieColor(i)}
                      opacity={active === null || active === i ? 1 : 0.35}
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-6 text-center">
              {active !== null ? (
                <>
                  <span className="line-clamp-2 type-body-sm text-muted-foreground">{slices[active].label}</span>
                  <span className="type-num-lg">{formatPercent(slices[active].pct)}</span>
                </>
              ) : (
                center && (
                  <>
                    <span className="type-caption text-muted-foreground">{center.label}</span>
                    <span className="type-num-body font-semibold">{center.value}</span>
                  </>
                )
              )}
            </div>
          </div>
          <ul className="max-h-80 space-y-0.5 overflow-y-auto type-body-sm" aria-label={`${title}: itens`}>
            {slices.map((s, i) => (
              <li key={s.key}>
                <button
                  type="button"
                  onMouseEnter={() => setActive(i)}
                  onMouseLeave={() => setActive(null)}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive(null)}
                  onClick={() => onPick?.(s)}
                  className={cn(
                    "flex min-h-9 w-full items-center gap-2 rounded-md px-2 text-left",
                    active === i && "bg-row-highlight",
                    !onPick && "cursor-default",
                  )}
                >
                  <span aria-hidden className="size-3 shrink-0 rounded-sm" style={{ background: pieColor(i) }} />
                  <span className="min-w-0 flex-1 truncate">{s.label}</span>
                  <span className="type-num-table text-muted-foreground">{formatPercent(s.pct)}</span>
                  <span className="w-28 text-right type-num-table">{formatBRL(s.value)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
