"use client";

// STORY-02-15 — alocação atual vs meta: pizza chart (Recharts) + tabela de desvios.
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { Card } from "@/components/ui";
import { formatBRL, formatPercent, formatPP } from "@/lib/format";
import { useAllocation } from "@/lib/portfolio";

// Paleta determinística por categoria (dark-friendly).
const COLORS = [
  "#6366f1",
  "#22c55e",
  "#f59e0b",
  "#ef4444",
  "#06b6d4",
  "#a855f7",
  "#84cc16",
];

export default function AllocationPage() {
  const { data, isLoading, isError } = useAllocation();

  const withValue = (data?.categories ?? []).filter((c) => c.valor_atual > 0);
  const pieData = withValue.map((c) => ({ name: c.category, value: c.valor_atual }));

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-2xl font-semibold text-foreground">
        Alocação vs. meta
      </h1>

      {isLoading && <p className="text-foreground/50">Carregando…</p>}
      {isError && <p className="text-loss">Erro ao carregar alocação.</p>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <p className="mb-4 text-sm text-foreground/50">
            Distribuição atual · {data ? formatBRL(data.total) : "—"}
          </p>
          {pieData.length === 0 ? (
            <p className="py-12 text-center text-sm text-foreground/40">
              Sem posições valoradas. Defina preços nas Posições.
            </p>
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    innerRadius={45}
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={entry.name} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => formatBRL(Number(value))}
                    contentStyle={{
                      background: "#16161a",
                      border: "1px solid #26262b",
                      borderRadius: "0.5rem",
                      color: "#e8e8ea",
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card>
          <p className="mb-4 text-sm text-foreground/50">Atual vs. meta por categoria</p>
          <div className="space-y-3">
            {(data?.categories ?? []).map((c) => (
              <div key={c.category} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-foreground/80">{c.category}</span>
                  <span className="tabular-nums text-foreground/60">
                    {formatPercent(c.pct_atual)}
                    {c.pct_meta != null && (
                      <span className="text-foreground/40">
                        {" "}/ {formatPercent(c.pct_meta)}
                      </span>
                    )}
                    {c.desvio_pp != null && (
                      <span
                        className={`ml-2 ${
                          c.desvio_pp >= 0 ? "text-gain" : "text-loss"
                        }`}
                      >
                        {formatPP(c.desvio_pp)}
                      </span>
                    )}
                  </span>
                </div>
                {/* barra: atual (cheia) com marcador da meta */}
                <div className="relative h-2 overflow-hidden rounded bg-muted">
                  <div
                    className="h-full rounded bg-accent/70"
                    style={{ width: `${Math.min(100, c.pct_atual)}%` }}
                  />
                  {c.pct_meta != null && (
                    <div
                      className="absolute top-0 h-full w-0.5 bg-foreground/70"
                      style={{ left: `${Math.min(100, c.pct_meta)}%` }}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
