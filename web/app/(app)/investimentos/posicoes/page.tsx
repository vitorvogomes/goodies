"use client";

// Investimentos › Posições (Story 7.1 — FR-21, FR-27, UX-DR9, UX-DR14): classes recolhidas,
// expansíveis para ativos, com aplicado e valor atual no fim do mês e o resultado do período da
// leitura. Cripto é o bloco "quanto saiu × quanto vale" (ativos só com valor). Preço velho: "preço de
// dd/mm/aaaa" com ponto de aviso; sem preço: "—" + "sem preço"; preço manual: Selo "manual".
// XIRR nominal × real do período por classe e consolidado; por ativo, % a.m. (Story 7.3).
// Alocação × meta ± banda e desvio em p.p. (Story 8.3); os ativos de objetivos no bloco "Objetivos",
// fora da base da alocação mas no patrimônio. Resultado total (desde o primeiro
// aporte) ao lado do resultado do período, XIRR com o equivalente ao mês e a explicação, a régua da
// banda e o cripto também em US$.
import { ChevronRightIcon } from "lucide-react";
import { Fragment, Suspense, useState } from "react";

import { PieBreakdown } from "@/components/charts/PieBreakdown";
import { Section } from "@/components/data/Section";
import { ReadingSelector, useLeitura } from "@/components/data/ReadingSelector";
import { AllocationCell } from "@/components/investimentos/AllocationCell";
import { OperationsBlock } from "@/components/investimentos/OperationsBlock";
import { StatusBadge } from "@/components/data/StatusBadge";
import { TrendArrow } from "@/components/data/TrendArrow";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  fmtQty,
  formatBRL,
  formatDate,
  formatMonth,
  formatPercent,
  formatSignedBRL,
  formatUnitPrice,
  formatUSD,
} from "@/lib/format";
import { usePositions } from "@/lib/positions";
import { usePeriodo } from "@/lib/use-periodo";
import { PHONE, useMedia } from "@/lib/use-media";
import { cn } from "@/lib/utils";
import type { Valued } from "@/types/overview";
import type { PositionAsset, PositionsReport } from "@/types/positions";

const LEITURA_LABEL = { mes: "do mês", tri: "do trimestre", ano: "do ano", inicio: "desde o início" };

function money(v: number | null): string {
  return v === null ? "—" : formatBRL(v);
}

function Result({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground">—</span>;
  return (
    <span className={cn("whitespace-nowrap", value > 0 && "text-positive", value < 0 && "text-negative")}>
      {value !== 0 && <TrendArrow up={value > 0} />}
      {formatSignedBRL(value)}
    </span>
  );
}

// XIRR do período (% a.a.): "aguardando IPCA" vira Selo (o IPCA do último mês ainda não saiu).
function Rate({
  v,
  monthly = null,
  short = false,
  ipcaNote,
  periodo,
}: {
  v: Valued;
  monthly?: number | null;
  short?: boolean; // mês/trimestre: o % a.m. vem primeiro (anualizar um mês exagera)
  ipcaNote: string;
  periodo?: string; // XIRR real: IPCA anterior ao fim do período = estimado com o último publicado
}) {
  if (v.value !== null) {
    const annual = `${formatPercent(v.value)} a.a.`;
    const month = monthly !== null ? `${formatPercent(monthly)} a.m.` : null;
    const estimated = periodo && v.source === "ipca" && v.as_of && v.as_of.slice(0, 7) < periodo;
    const [main, sub] = estimated
      ? [annual, `IPCA até ${formatMonth(v.as_of!.slice(0, 7))} · estimado`]
      : short && month
        ? [month, `≈ ${annual}`]
        : [annual, month && `≈ ${month}`];
    return (
      <span className="inline-flex flex-col items-end whitespace-nowrap">
        <span>{main}</span>
        {sub && <span className="type-caption font-normal text-muted-foreground">{sub}</span>}
      </span>
    );
  }
  if (v.unavailable_reason === "aguardando_ipca") {
    return <StatusBadge tooltip={ipcaNote}>aguardando IPCA</StatusBadge>;
  }
  return <span className="text-muted-foreground">—</span>;
}

// O IPCA de um mês sai por volta do dia 10 do mês seguinte (IBGE).
function ipcaNote(periodo: string): string {
  const [y, m] = periodo.split("-").map(Number);
  const next = m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, "0")}`;
  return `O IPCA de ${formatMonth(periodo)} sai por volta de 10/${next.slice(5)}/${next.slice(0, 4)} (IBGE); até lá a rentabilidade real fica aguardando.`;
}

const XIRR_HELP =
  "XIRR: a taxa anual que iguala o que você aplicou — cada aporte na data dele — ao valor no fim do período. " +
  "Considera quanto tempo cada real ficou investido (o rendimento ponderado pelo prazo). Num período curto, " +
  "um mês de +1% vira ≈ 12,7% a.a.: por isso ao lado vai o equivalente ao mês.";

function HeaderHelp({ label, help }: { label: string; help: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" className="underline decoration-dotted underline-offset-4">
          {label}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-80">{help}</TooltipContent>
    </Tooltip>
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
      {a.valor_usd != null && <span className="type-num-table text-muted-foreground">{formatUSD(a.valor_usd)}</span>}
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
  const byPeriod = leitura !== "inicio"; // desde o início, o resultado do período é o total
  const short = leitura === "mes" || leitura === "tri";
  const note = ipcaNote(periodo);
  const phone = useMedia(PHONE);
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
        <div className="h-80 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />
      ) : phone ? (
        <PhonePositions data={data} byPeriod={byPeriod} short={short} note={note} leitura={leitura} />
      ) : (
        <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card" tabIndex={0} role="region" aria-label="Posições">
          <table className="w-full type-body-sm">
            <caption className="sr-only">Posições por classe e ativo</caption>
            <thead className="bg-muted text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 text-left font-medium">Classe / ativo</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Aplicado</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Valor atual</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  <HeaderHelp
                    label="Resultado total"
                    help="Valor atual − aplicado + proventos, desde o primeiro aporte. No bloco cripto: quanto vale − quanto saiu."
                  />
                </th>
                {byPeriod && (
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    Resultado {LEITURA_LABEL[leitura]}
                  </th>
                )}
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  <HeaderHelp label="XIRR" help={XIRR_HELP} />
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  <HeaderHelp
                    label="XIRR real"
                    help="O XIRR descontado o IPCA do período (o ganho acima da inflação). Enquanto o IPCA do último mês não sai (IBGE, por volta do dia 10), usa o último publicado e marca “estimado”; recalcula quando o oficial sai."
                  />
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  <HeaderHelp
                    label="Alocação × meta"
                    help="A régua mostra a faixa aceita (meta ± banda, em verde claro) e o ponto é a alocação de hoje. Fora da faixa, o ponto e o texto ficam laranja: é a classe a reforçar (abaixo) ou a segurar (acima) no aporte."
                  />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.classes.map((c) => (
                <Fragment key={c.key}>
                  <tr className="font-semibold">
                    <th scope="row" className="px-3 py-2 text-left">
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
                    <td className="px-3 py-2 text-right type-num-table">{money(c.aplicado)}</td>
                    <td className="px-3 py-2 text-right type-num-table">
                      <span className="inline-flex flex-col items-end">
                        {formatBRL(c.valor)}
                        {c.valor_usd != null && (
                          <span className="type-num-table font-normal text-muted-foreground">{formatUSD(c.valor_usd)}</span>
                        )}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right type-num-table">
                      <Result value={c.resultado_total} />
                    </td>
                    {byPeriod && (
                      <td className="px-3 py-2 text-right type-num-table">
                        <Result value={c.resultado} />
                      </td>
                    )}
                    <td className="px-3 py-2 text-right type-num-table">
                      <Rate v={c.xirr_nominal} monthly={c.xirr_mensal} short={short} ipcaNote={note} />
                    </td>
                    <td className="px-3 py-2 text-right type-num-table">
                      <Rate v={c.xirr_real} ipcaNote={note} periodo={periodo} />
                    </td>
                    <td className="px-3 py-2 text-right type-num-table">
                      <AllocationCell alocacao={c.alocacao} meta={c.meta} banda={c.banda} desvio={c.desvio_pp} fora={c.fora_banda} />
                    </td>
                  </tr>
                  {open.has(c.key) &&
                    c.assets.map((a) => (
                      <tr key={`${c.key}-${a.symbol}`}>
                        <th scope="row" className="py-1.5 pr-3 pl-8 text-left font-normal">
                          <span className="inline-flex items-center gap-2">
                            <span className="type-num-table">{a.symbol}</span>
                            {a.manual && <StatusBadge tooltip="Preço informado à mão.">manual</StatusBadge>}
                          </span>
                          {a.quantidade !== null && (
                            <span className="block type-caption text-muted-foreground type-num-table">
                              {fmtQty(Number(a.quantidade))}
                              {a.preco !== null && ` × R$ ${formatUnitPrice(String(a.preco))}`}
                              {a.preco_usd != null && ` · US$ ${formatUnitPrice(String(a.preco_usd))}`}
                            </span>
                          )}
                          {a.nota && <span className="block type-caption text-muted-foreground">{a.nota}</span>}
                        </th>
                        <td className="px-3 py-1.5 text-right type-num-table">{money(a.aplicado)}</td>
                        <td className="px-3 py-1.5 text-right type-num-table">
                          <AssetValue a={a} />
                        </td>
                        <td className="px-3 py-1.5 text-right type-num-table">
                          <Result value={a.resultado_total} />
                        </td>
                        {byPeriod && (
                          <td className="px-3 py-1.5 text-right type-num-table">
                            <Result value={a.resultado} />
                          </td>
                        )}
                        <td className="px-3 py-1.5 text-right type-num-table text-muted-foreground" colSpan={2}>
                          {a.xirr_mensal !== null ? `${formatPercent(a.xirr_mensal)} a.m.` : "—"}
                        </td>
                        <td className="px-3 py-1.5 text-right type-num-table text-muted-foreground">
                          <AllocationCell alocacao={a.alocacao} meta={a.meta} banda={null} desvio={a.desvio_pp} fora={false} compact />
                        </td>
                      </tr>
                    ))}
                </Fragment>
              ))}
            </tbody>
            <tbody className="border-t border-border">
              <tr>
                <th scope="row" className="px-3 py-2 text-left font-normal">
                  Caixa em corretora <span className="type-caption text-muted-foreground">no patrimônio</span>
                </th>
                <td />
                <td className="px-3 py-2 text-right type-num-table">{formatBRL(data.caixa_corretora)}</td>
                <td colSpan={byPeriod ? 5 : 4} />
              </tr>
              {data.a_caminho.map((w) => (
                <tr key={w.broker} className="text-muted-foreground">
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    <span className="inline-flex flex-wrap items-center gap-2">
                      A caminho da {w.broker}
                      <StatusBadge tone="warning">a caminho</StatusBadge>
                      {w.import_from && (
                        <span className="type-caption">importe o relatório B3 a partir de {formatDate(w.import_from)}</span>
                      )}
                    </span>
                  </th>
                  <td />
                  <td className="px-3 py-2 text-right type-num-table">{formatBRL(w.value)}</td>
                  <td colSpan={byPeriod ? 5 : 4} className="px-3 py-2 type-caption">fora do patrimônio</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t border-foreground font-semibold">
              <tr>
                <th scope="row" className="px-3 py-2 text-left">Total</th>
                <td className="px-3 py-2 text-right type-num-table">{formatBRL(data.aplicado)}</td>
                <td className="px-3 py-2 text-right type-num-table">{formatBRL(data.total)}</td>
                <td className="px-3 py-2 text-right type-num-table">
                  <Result value={data.resultado_total} />
                </td>
                {byPeriod && <td />}
                <td className="px-3 py-2 text-right type-num-table">
                  <Rate v={data.xirr_nominal} monthly={data.xirr_mensal} short={short} ipcaNote={note} />
                </td>
                <td className="px-3 py-2 text-right type-num-table">
                  <Rate v={data.xirr_real} ipcaNote={note} periodo={periodo} />
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
      {data && <PortfolioPie report={data} />}
      <OperationsBlock />
    </div>
  );
}

// Celular (v2.2): um cartão por classe — valor, resultado, rentabilidade e alocação × meta; os
// ativos abrem no toque, com valor, quantidade × preço e resultado. O total fecha a lista.
function PhonePositions({
  data,
  byPeriod,
  short,
  note,
  leitura,
}: {
  data: PositionsReport;
  byPeriod: boolean;
  short: boolean;
  note: string;
  leitura: keyof typeof LEITURA_LABEL;
}) {
  return (
    <div className="space-y-2">
      {data.classes.map((c) => (
        <Section
          key={c.key}
          title={c.is_bucket ? "Cripto" : c.label}
          summary={<span className="type-num-body text-foreground">{formatBRL(c.valor)}</span>}
        >
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 type-body-sm">
            <div>
              <dt className="type-caption text-muted-foreground">Resultado total</dt>
              <dd className="type-num-table">
                <Result value={c.resultado_total} />
              </dd>
            </div>
            {byPeriod && (
              <div>
                <dt className="type-caption text-muted-foreground">Resultado {LEITURA_LABEL[leitura]}</dt>
                <dd className="type-num-table">
                  <Result value={c.resultado} />
                </dd>
              </div>
            )}
            <div>
              <dt className="type-caption text-muted-foreground">Aplicado</dt>
              <dd className="type-num-table">{money(c.aplicado)}</dd>
            </div>
            {c.valor_usd != null && (
              <div>
                <dt className="type-caption text-muted-foreground">Em dólar</dt>
                <dd className="type-num-table">{formatUSD(c.valor_usd)}</dd>
              </div>
            )}
            <div>
              <dt className="type-caption text-muted-foreground">XIRR</dt>
              <dd className="type-num-table [&>span]:items-start">
                <Rate v={c.xirr_nominal} monthly={c.xirr_mensal} short={short} ipcaNote={note} />
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="type-caption text-muted-foreground">Alocação × meta</dt>
              <dd>
                <AllocationCell alocacao={c.alocacao} meta={c.meta} banda={c.banda} desvio={c.desvio_pp} fora={c.fora_banda} />
              </dd>
            </div>
          </dl>
          {c.assets.length > 0 && (
            <ul className="mt-3 divide-y divide-border border-t border-border">
              {c.assets.map((a) => (
                <li key={a.symbol} className="flex items-start justify-between gap-3 py-2">
                  <span className="min-w-0">
                    <span className="block type-num-table">{a.symbol}</span>
                    {a.quantidade !== null && (
                      <span className="block type-caption text-muted-foreground">
                        {fmtQty(Number(a.quantidade))}
                        {a.preco !== null && ` × R$ ${formatUnitPrice(String(a.preco))}`}
                        {a.preco_usd != null && ` · US$ ${formatUnitPrice(String(a.preco_usd))}`}
                      </span>
                    )}
                    {a.nota && <span className="block type-caption text-muted-foreground">{a.nota}</span>}
                  </span>
                  <span className="flex flex-col items-end text-right type-num-table">
                    <AssetValue a={a} />
                    <Result value={a.resultado_total} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      ))}
      <div className="space-y-1 rounded-lg border border-border bg-card p-card-padding shadow-card type-body-sm">
        <p className="flex justify-between gap-2">
          <span className="text-muted-foreground">Caixa em corretora</span>
          <span className="type-num-table">{formatBRL(data.caixa_corretora)}</span>
        </p>
        {data.a_caminho.map((w) => (
          <p key={w.broker} className="flex justify-between gap-2 text-muted-foreground">
            <span>A caminho da {w.broker} (fora do patrimônio)</span>
            <span className="type-num-table">{formatBRL(w.value)}</span>
          </p>
        ))}
        <p className="flex justify-between gap-2 border-t border-border pt-2 font-semibold">
          <span>Total</span>
          <span className="type-num-body">{formatBRL(data.total)}</span>
        </p>
        <p className="flex justify-between gap-2">
          <span className="text-muted-foreground">Resultado total</span>
          <span className="type-num-table">
            <Result value={data.resultado_total} />
          </span>
        </p>
        <p className="flex justify-between gap-2">
          <span className="text-muted-foreground">XIRR</span>
          <span className="type-num-table">
            <Rate v={data.xirr_nominal} monthly={data.xirr_mensal} short={short} ipcaNote={note} />
          </span>
        </p>
      </div>
    </div>
  );
}

// Pizza da carteira (v2.2): % de cada classe (e do caixa na corretora) ou de cada ativo no total.
function PortfolioPie({ report }: { report: PositionsReport }) {
  const [by, setBy] = useState<"classes" | "ativos">("classes");
  const slices = (by === "classes" ? report.distribuicao : report.distribuicao_ativos) ?? [];
  return (
    <PieBreakdown
      id="pizza-carteira"
      title="Distribuição da carteira"
      slices={slices}
      center={{ label: "total", value: formatBRL(report.total) }}
      actions={
        <div role="group" aria-label="Ver por" className="flex rounded-md bg-muted p-0.5 type-body-sm">
          {(["classes", "ativos"] as const).map((k) => (
            <button
              key={k}
              type="button"
              aria-pressed={by === k}
              onClick={() => setBy(k)}
              className={cn("min-h-8 rounded-sm px-2 text-foreground", by === k && "bg-background font-semibold shadow-xs")}
            >
              {k === "classes" ? "Classes" : "Ativos"}
            </button>
          ))}
        </div>
      }
    />
  );
}

export default function PosicoesPage() {
  return (
    <Suspense>
      <Posicoes />
    </Suspense>
  );
}
