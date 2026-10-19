"use client";

// Os três gráficos do Histórico (Story 9.3 — FR-34, AR25, UX-DR42; DESIGN › chart-net-worth,
// chart-spending, chart-contribution): patrimônio (linha 2px chart-1, aplicado tracejado chart-3,
// grade só horizontal, sem área, lacuna onde o patrimônio não é coberto), gastos por grupo (barras
// horizontais no estilo do aporte: período chart-1 (o verde), anterior chart-2
// mais fina, média 12m como marcador tracejado, rótulo direto; clicar abre as transações do grupo) e aporte planejado × realizado (barras
// agrupadas, média 12m do realizado como marcador chart-3). Cada um com "Ver como tabela". Eixos em
// moeda completa, sem animação; as séries se distinguem também por estilo e legenda.
import { useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { useHistory, useSeries } from "@/lib/closing";
import { formatBRL, formatMonth } from "@/lib/format";
import type { HistoryRow, SeriesPoint } from "@/types/closing";

const C1 = "var(--color-chart-1)";
const C2 = "var(--color-chart-2)";
const C3 = "var(--color-chart-3)";
const AXIS = { fontSize: 12, fill: "var(--color-muted-foreground)" };

function money(v: number | null | undefined): string {
  return v == null ? "—" : formatBRL(v);
}

function ChartCard({
  id,
  title,
  table,
  children,
}: {
  id: string;
  title: string;
  table: ReactNode;
  children: ReactNode;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <section aria-labelledby={id} className="space-y-2 rounded-lg border border-border bg-card shadow-card p-card-padding">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={id} className="type-section-title">
          {title}
        </h3>
        <Button size="sm" variant="ghost" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
          {asTable ? "Ver como gráfico" : "Ver como tabela"}
        </Button>
      </div>
      {asTable ? table : children}
    </section>
  );
}

function SimpleTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full type-body-sm">
        <thead className="text-muted-foreground">
          <tr>
            {head.map((h, i) => (
              <th key={h} scope="col" className={i === 0 ? "py-1 text-left font-medium" : "py-1 text-right font-medium"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => (
            <tr key={String(r[0])}>
              {r.map((c, i) =>
                i === 0 ? (
                  <th key={i} scope="row" className="py-1 text-left font-normal">
                    {c}
                  </th>
                ) : (
                  <td key={i} className="py-1 text-right type-num-table">
                    {c}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NetWorth({ points }: { points: SeriesPoint[] }) {
  const data = points.map((p) => ({ mes: formatMonth(p.month.slice(0, 7)), patrimonio: p.patrimonio, aplicado: p.aplicado }));
  return (
    <ChartCard
      id="grafico-patrimonio"
      title="Patrimônio"
      table={
        <SimpleTable
          head={["Mês", "Patrimônio", "Aplicado"]}
          rows={data.map((d) => [d.mes, d.patrimonio == null ? "patrimônio não coberto" : money(d.patrimonio), money(d.aplicado)])}
        />
      }
    >
      <div className="h-72" role="img" aria-label="Gráfico de patrimônio e aplicado por mês">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 16 }}>
            <CartesianGrid vertical={false} stroke="var(--color-border)" />
            <XAxis dataKey="mes" tick={AXIS} />
            <YAxis tick={AXIS} tickFormatter={(v: number) => formatBRL(v)} width={110} />
            <Tooltip formatter={(v) => money(Number(v))} isAnimationActive={false} />
            <Legend />
            <Line
              name="Patrimônio"
              dataKey="patrimonio"
              stroke={C1}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              name="Aplicado"
              dataKey="aplicado"
              stroke={C3}
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

// Média 12m de cada grupo: um traço vertical no fim do valor (marcador, não barra).
function AverageMarker(props: { x?: number; y?: number; width?: number; height?: number }) {
  const { x = 0, y = 0, width = 0, height = 0 } = props;
  return (
    <line x1={x + width} x2={x + width} y1={y - 6} y2={y + height + 6} stroke={C3} strokeWidth={2} strokeDasharray="2 2" />
  );
}

// O clique abre as transações do grupo — Caixa › Transações é de um mês: só na leitura "mês" a
// lista bate com a barra.
function Spending({ groups, periodo, clickable }: { groups: HistoryRow[]; periodo: string; clickable: boolean }) {
  const router = useRouter();
  const data = groups.map((g) => ({
    key: g.key.replace(/^grupo:/, ""),
    grupo: g.label,
    periodo: g.current ?? 0,
    anterior: g.previous,
    media: g.average,
  }));
  const open = (key: string) => router.push(`/caixa/transacoes?periodo=${periodo}&grupo=${encodeURIComponent(key)}`);
  return (
    <ChartCard
      id="grafico-gastos"
      title="Gastos por grupo"
      table={
        <SimpleTable
          head={["Grupo", "Período", "Anterior", "Média 12m"]}
          rows={data.map((d) => [d.grupo, money(d.periodo), money(d.anterior), money(d.media)])}
        />
      }
    >
      <div style={{ height: Math.max(180, data.length * 52) }} role="img" aria-label="Gastos por grupo: período, anterior e média 12m">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 120, bottom: 4, left: 16 }} barGap={3} barCategoryGap="22%">
            <CartesianGrid horizontal={false} stroke="var(--color-border)" />
            <XAxis type="number" tick={AXIS} tickFormatter={(v: number) => formatBRL(v)} />
            <YAxis type="category" dataKey="grupo" tick={AXIS} width={140} />
            <Tooltip formatter={(v) => money(Number(v))} cursor={{ fill: "var(--color-muted)" }} isAnimationActive={false} />
            <Bar
              name="Período"
              dataKey="periodo"
              fill={C1}
              radius={[0, 3, 3, 0]}
              barSize={14}
              isAnimationActive={false}
              cursor={clickable ? "pointer" : undefined}
              onClick={clickable ? (d) => open((d as unknown as { key: string }).key) : undefined}
            >
              <LabelList dataKey="periodo" position="right" formatter={(v) => money(Number(v))} style={AXIS} />
            </Bar>
            <Bar name="Anterior" dataKey="anterior" fill={C2} radius={[0, 3, 3, 0]} barSize={8} isAnimationActive={false} />
            <Bar name="Média 12m" dataKey="media" fill="transparent" shape={AverageMarker} isAnimationActive={false} legendType="line" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {/* legenda própria: anterior (só contorno) e média (marcador) não têm cor de preenchimento */}
      <ul className="flex flex-wrap gap-x-4 gap-y-1 type-caption text-muted-foreground">
        <li className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-2.5 w-4 rounded-sm" style={{ background: C1 }} />
          Período
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-1.5 w-4 rounded-sm" style={{ background: C2 }} />
          Anterior
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-3 w-0 border-l-2 border-dashed" style={{ borderColor: C3 }} />
          Média 12m
        </li>
      </ul>
      {clickable && <p className="type-caption text-muted-foreground">Clique numa barra para ver as transações do grupo.</p>}
    </ChartCard>
  );
}

function Contribution({ points, media }: { points: SeriesPoint[]; media: number | null }) {
  const last = points.slice(-12);
  const hasPlanned = last.some((p) => p.planejado != null);
  const data = last.map((p) => ({ mes: formatMonth(p.month.slice(0, 7)), planejado: p.planejado, realizado: p.realizado }));
  return (
    <ChartCard
      id="grafico-aporte"
      title="Aporte planejado × realizado"
      table={
        <SimpleTable
          head={hasPlanned ? ["Mês", "Planejado", "Realizado"] : ["Mês", "Realizado"]}
          rows={data.map((d) => (hasPlanned ? [d.mes, money(d.planejado), money(d.realizado)] : [d.mes, money(d.realizado)]))}
        />
      }
    >
      <div className="h-72" role="img" aria-label="Aporte planejado e realizado por mês, com a média 12m do realizado">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 16 }}>
            <CartesianGrid vertical={false} stroke="var(--color-border)" />
            <XAxis dataKey="mes" tick={AXIS} />
            <YAxis tick={AXIS} tickFormatter={(v: number) => formatBRL(v)} width={110} />
            <Tooltip formatter={(v) => money(Number(v))} isAnimationActive={false} />
            <Legend />
            {hasPlanned && <Bar name="Planejado" dataKey="planejado" fill={C2} isAnimationActive={false} />}
            <Bar name="Realizado" dataKey="realizado" fill={C1} isAnimationActive={false} />
            {media != null && (
              <ReferenceLine
                y={media}
                stroke={C3}
                strokeWidth={2}
                strokeDasharray="2 3"
                label={{ value: `média 12m ${formatBRL(media)}`, position: "insideTopRight", fill: "var(--color-muted-foreground)", fontSize: 12 }}
              />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

export function HistoryCharts({ periodo, leitura }: { periodo: string; leitura: string }) {
  const series = useSeries(periodo);
  const history = useHistory(periodo, leitura);
  if ((series.isError && !series.data) || (history.isError && !history.data)) {
    return <p className="type-body text-negative">Não foi possível carregar os gráficos.</p>;
  }
  if (!series.data || !history.data) {
    return <div className="h-72 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />;
  }
  const points = series.data.points;
  return (
    <div className="space-y-card-gap">
      {points.length > 0 ? (
        <NetWorth points={points} />
      ) : (
        <p className="rounded-lg border border-border bg-card shadow-card p-card-padding type-body text-muted-foreground">
          Disponível a partir do primeiro mês fechado na v2.
        </p>
      )}
      {history.data.groups.length > 0 && (
        <Spending groups={history.data.groups} periodo={periodo} clickable={leitura === "mes"} />
      )}
      {points.length > 0 && <Contribution points={points} media={series.data.realizado_media12} />}
    </div>
  );
}
