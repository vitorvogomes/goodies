"use client";

// Investimentos › Posições (Story 7.1 — FR-21, FR-27, UX-DR9, UX-DR14): classes recolhidas,
// expansíveis para ativos, com aplicado e valor atual no fim do mês e o resultado do período da
// leitura. Cripto é o bloco "quanto saiu × quanto vale" (ativos só com valor). Preço velho: "preço de
// dd/mm/aaaa" com ponto de aviso; sem preço: "—" + "sem preço"; preço manual: Selo "manual".
// XIRR nominal × real do período por classe e consolidado; por ativo, % a.m. (Story 7.3).
// Alocação × meta ± banda e desvio em p.p. (Story 8.3); os ativos de objetivos no bloco "Objetivos",
// fora da base da alocação mas no patrimônio.
import { ChevronRightIcon } from "lucide-react";
import { Fragment, Suspense, useState } from "react";

import { ReadingSelector, useLeitura } from "@/components/data/ReadingSelector";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/button";
import { formatBRL, formatDate, formatMonth, formatPercent, formatPP, formatSignedBRL } from "@/lib/format";
import { usePositions } from "@/lib/positions";
import { usePeriodo } from "@/lib/use-periodo";
import { cn } from "@/lib/utils";
import type { Valued } from "@/types/overview";
import type { PositionAsset } from "@/types/positions";

const LEITURA_LABEL = { mes: "do mês", tri: "do trimestre", ano: "do ano", inicio: "desde o início" };

function money(v: number | null): string {
  return v === null ? "—" : formatBRL(v);
}

function Result({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground">—</span>;
  return (
    <span className={cn(value > 0 && "text-positive", value < 0 && "text-negative")}>
      {value !== 0 && <span aria-hidden>{value > 0 ? "▲ " : "▼ "}</span>}
      {formatSignedBRL(value)}
    </span>
  );
}

// XIRR do período (% a.a.): "aguardando IPCA" vira Selo (o IPCA do último mês ainda não saiu).
function Rate({ v }: { v: Valued }) {
  if (v.value !== null) return <span>{formatPercent(v.value)}</span>;
  if (v.unavailable_reason === "aguardando_ipca") {
    return <StatusBadge tooltip="o IPCA do último mês do período ainda não saiu">aguardando IPCA</StatusBadge>;
  }
  return <span className="text-muted-foreground">—</span>;
}

// Story 8.3: alocação atual × meta ± banda e o desvio em p.p. (coluna própria, sem seta); fora da
// banda, o desvio sai em laranja. Classe: % na base sem os objetivos; ativo: % dentro da classe.
function Allocation({
  alocacao,
  meta,
  banda,
  desvio,
  fora,
  muted = false,
}: {
  alocacao: number | null;
  meta: number | null;
  banda: number | null;
  desvio: number | null;
  fora: boolean;
  muted?: boolean;
}) {
  const cell = cn("px-4 text-right type-num-table", muted ? "py-1.5 text-muted-foreground" : "py-2");
  return (
    <>
      <td className={cell}>{alocacao != null ? formatPercent(alocacao) : "—"}</td>
      <td className={cell}>
        {meta != null ? `${formatPercent(meta)}${banda != null ? ` ± ${String(banda).replace(".", ",")} p.p.` : ""}` : "—"}
      </td>
      <td className={cn(cell, fora && "text-warning")}>
        {desvio != null ? formatPP(desvio) : "—"}
        {fora && <span className="sr-only"> (fora da banda)</span>}
      </td>
    </>
  );
}

function AssetValue({ a }: { a: PositionAsset }) {
  if (a.valor.value === null) {
    return (
      <span className="text-muted-foreground">
        — <span className="type-caption">sem preço</span>
      </span>
    );
  }
  return (
    <span className="inline-flex flex-col items-end">
      <span>{formatBRL(a.valor.value)}</span>
      {a.valor.stale && a.valor.as_of && (
        <span className="inline-flex items-center gap-1 type-caption text-muted-foreground">
          <span aria-hidden className="size-1.5 rounded-full bg-warning-dot" />
          preço de {formatDate(a.valor.as_of)}
        </span>
      )}
    </span>
  );
}

function Posicoes() {
  const { periodo } = usePeriodo();
  const leitura = useLeitura();
  const report = usePositions(periodo, leitura);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (k: string) =>
    setOpen((s) => {
      const next = new Set(s);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  const data = report.data;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="type-section-title">
          Posições em {formatMonth(periodo)}{" "}
          <span className="type-body-sm font-normal text-muted-foreground">
            · resultado {LEITURA_LABEL[leitura]}
          </span>
        </h2>
        <ReadingSelector />
      </div>
      {report.isError ? (
        <div role="alert" className="flex items-center gap-2 type-body text-negative">
          Não foi possível carregar as posições.
          <Button size="sm" variant="secondary" onClick={() => report.refetch()}>
            Tentar de novo
          </Button>
        </div>
      ) : !data ? (
        <div className="h-80 animate-pulse rounded-lg border border-border bg-card" aria-hidden />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card" tabIndex={0} role="region" aria-label="Posições">
          <table className="w-full type-body-sm">
            <caption className="sr-only">Posições por classe e ativo</caption>
            <thead className="bg-muted text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 text-left font-medium">Classe / ativo</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Aplicado</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Valor atual</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Resultado</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">XIRR nominal</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">XIRR real</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Alocação</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Meta</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Desvio</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.classes.map((c) => (
                <Fragment key={c.key}>
                  <tr className="font-semibold">
                    <th scope="row" className="px-4 py-2 text-left">
                      <button
                        type="button"
                        aria-expanded={open.has(c.key)}
                        disabled={c.assets.length === 0}
                        className="inline-flex items-center gap-1 disabled:text-muted-foreground"
                        onClick={() => toggle(c.key)}
                      >
                        <ChevronRightIcon
                          aria-hidden
                          className={cn("size-3.5 transition-transform", open.has(c.key) && "rotate-90")}
                        />
                        {c.label}
                      </button>
                    </th>
                    <td className="px-4 py-2 text-right type-num-table">{money(c.aplicado)}</td>
                    <td className="px-4 py-2 text-right type-num-table">{formatBRL(c.valor)}</td>
                    <td className="px-4 py-2 text-right type-num-table">
                      <Result value={c.resultado} />
                    </td>
                    <td className="px-4 py-2 text-right type-num-table">
                      <Rate v={c.xirr_nominal} />
                    </td>
                    <td className="px-4 py-2 text-right type-num-table">
                      <Rate v={c.xirr_real} />
                    </td>
                    <Allocation alocacao={c.alocacao} meta={c.meta} banda={c.banda} desvio={c.desvio_pp} fora={c.fora_banda} />
                  </tr>
                  {open.has(c.key) &&
                    c.assets.map((a) => (
                      <tr key={`${c.key}-${a.symbol}`}>
                        <th scope="row" className="py-1.5 pr-4 pl-10 text-left font-normal">
                          <span className="inline-flex items-center gap-2">
                            <span className="type-num-table">{a.symbol}</span>
                            {a.manual && <StatusBadge tooltip="Preço informado à mão.">manual</StatusBadge>}
                          </span>
                          {a.nota && <span className="block type-caption text-muted-foreground">{a.nota}</span>}
                        </th>
                        <td className="px-4 py-1.5 text-right type-num-table">{money(a.aplicado)}</td>
                        <td className="px-4 py-1.5 text-right type-num-table">
                          <AssetValue a={a} />
                        </td>
                        <td className="px-4 py-1.5 text-right type-num-table">
                          <Result value={a.resultado} />
                        </td>
                        <td className="px-4 py-1.5 text-right type-num-table text-muted-foreground" colSpan={2}>
                          {a.xirr_mensal !== null ? `${formatPercent(a.xirr_mensal)} a.m.` : "—"}
                        </td>
                        <Allocation alocacao={a.alocacao} meta={a.meta} banda={null} desvio={a.desvio_pp} fora={false} muted />
                      </tr>
                    ))}
                </Fragment>
              ))}
            </tbody>
            <tbody className="border-t border-border">
              <tr>
                <th scope="row" className="px-4 py-2 text-left font-normal">
                  Caixa em corretora <span className="type-caption text-muted-foreground">no patrimônio</span>
                </th>
                <td />
                <td className="px-4 py-2 text-right type-num-table">{formatBRL(data.caixa_corretora)}</td>
                <td colSpan={6} />
              </tr>
              {data.a_caminho.map((w) => (
                <tr key={w.broker} className="text-muted-foreground">
                  <th scope="row" className="px-4 py-2 text-left font-normal">
                    <span className="inline-flex flex-wrap items-center gap-2">
                      A caminho da {w.broker}
                      <StatusBadge tone="warning">a caminho</StatusBadge>
                      {w.import_from && (
                        <span className="type-caption">importe o relatório B3 a partir de {formatDate(w.import_from)}</span>
                      )}
                    </span>
                  </th>
                  <td />
                  <td className="px-4 py-2 text-right type-num-table">{formatBRL(w.value)}</td>
                  <td colSpan={6} className="px-4 py-2 type-caption">fora do patrimônio</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t border-foreground font-semibold">
              <tr>
                <th scope="row" className="px-4 py-2 text-left">Total</th>
                <td className="px-4 py-2 text-right type-num-table">{formatBRL(data.aplicado)}</td>
                <td className="px-4 py-2 text-right type-num-table">{formatBRL(data.total)}</td>
                <td />
                <td className="px-4 py-2 text-right type-num-table">
                  <Rate v={data.xirr_nominal} />
                </td>
                <td className="px-4 py-2 text-right type-num-table">
                  <Rate v={data.xirr_real} />
                </td>
                <td colSpan={3} />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

export default function PosicoesPage() {
  return (
    <Suspense>
      <Posicoes />
    </Suspense>
  );
}
