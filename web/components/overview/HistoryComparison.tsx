"use client";

// Histórico do fluxo (Story 9.1 — FR-34, UX-DR9, UX-DR15): o período da leitura × o anterior × a
// média 12m em receitas, gastos por grupo, taxa de poupança e aporte planejado × realizado, com o
// Selo de variação. "Desde o início" mostra o acumulado, sem comparação. Tudo da API (AD-4).
import { DateStamp } from "@/components/data/DateStamp";
import { VariationBadge } from "@/components/data/VariationBadge";
import { Button } from "@/components/ui/button";
import { useHistory } from "@/lib/closing";
import { formatBRL, formatPercent } from "@/lib/format";
import type { HistoryRow } from "@/types/closing";

// gasto que sobe é ruim; o resto (receita, poupança, aporte) é bom subir
const GOOD_DOWN = new Set(["gastos"]);

function value(row: HistoryRow, v: number | null): string {
  if (v === null) return "—";
  return row.kind === "pct" ? formatPercent(v) : formatBRL(v);
}

function Table({
  caption,
  rows,
  compare,
  previousLabel,
  averageMonths,
  groups = false,
}: {
  caption: string;
  rows: HistoryRow[];
  compare: boolean;
  previousLabel: string | null;
  averageMonths: number;
  groups?: boolean;
}) {
  const cell = "px-4 py-2 text-right type-num-table";
  return (
    <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card">
      <table className="w-full type-body-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2 text-left font-medium">
              {groups ? "Grupo" : "Item"}
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              {compare ? "Período" : "Acumulado"}
            </th>
            {compare && (
              <>
                <th scope="col" className="px-4 py-2 text-right font-medium">
                  Anterior{previousLabel ? ` (${previousLabel})` : ""}
                </th>
                <th scope="col" className="px-4 py-2 text-right font-medium">
                  × anterior
                </th>
                <th scope="col" className="px-4 py-2 text-right font-medium">
                  Média 12m{averageMonths && averageMonths < 12 ? ` (${averageMonths} meses)` : ""}
                </th>
                <th scope="col" className="px-4 py-2 text-right font-medium">
                  × média
                </th>
              </>
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => {
            const good = groups || GOOD_DOWN.has(r.key) ? "down" : "up";
            const unit = r.kind === "pct" ? "p.p." : "%";
            return (
              <tr key={r.key}>
                <th scope="row" className="px-4 py-2 text-left font-normal">
                  {r.label}
                </th>
                <td className={cell}>{value(r, r.current)}</td>
                {compare && (
                  <>
                    <td className={cell}>{value(r, r.previous)}</td>
                    <td className={cell}>
                      <VariationBadge value={r.var_previous} unit={unit} good={good} />
                    </td>
                    <td className={cell}>{value(r, r.average)}</td>
                    <td className={cell}>
                      <VariationBadge value={r.var_average} unit={unit} good={good} />
                    </td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function HistoryComparison({ periodo, leitura }: { periodo: string; leitura: string }) {
  const history = useHistory(periodo, leitura);
  if (history.isError && !history.data) {
    return (
      <div role="alert" className="flex items-center gap-2 type-body text-negative">
        Não foi possível carregar o histórico.
        <Button size="sm" variant="secondary" onClick={() => history.refetch()}>
          Tentar de novo
        </Button>
      </div>
    );
  }
  const data = history.data;
  if (!data) return <div className="h-64 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />;
  const compare = data.leitura !== "inicio";
  return (
    <section aria-labelledby="historico-fluxo" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="historico-fluxo" className="type-section-title">
          {compare ? "Período × anterior × média 12m" : "Desde o início"}
        </h2>
        <span className="inline-flex items-center gap-2">
          {data.stale && <span className="type-caption text-warning">receita do trabalho ainda sem o mês todo</span>}
          <DateStamp asOf={data.as_of} source="ledger" />
        </span>
      </div>
      <Table
        caption="Fluxo do período"
        rows={data.rows}
        compare={compare}
        previousLabel={data.previous_label}
        averageMonths={data.average_months}
      />
      {data.groups.length > 0 && (
        <Table
          caption="Gastos por grupo"
          rows={data.groups}
          compare={compare}
          previousLabel={data.previous_label}
          averageMonths={data.average_months}
          groups
        />
      )}
    </section>
  );
}
