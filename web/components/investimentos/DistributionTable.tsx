"use client";

// Distribuição do aporte (Story 8.5 — FR-29, UX-DR38, DESIGN › allocation-distribution): os
// objetivos (progresso até o alvo, "Snow Trip · R$ 350/mês para chegar em jul/2027") e as classes
// recolhidas, expansíveis para ativos, com meta, atual, desvio (p.p.), banda e sugerido — tudo de
// `POST /api/v1/planning/distribution/preview` (o front não calcula). Pisos reduzidos → a nota.
// Story 8.6: o sugerido se edita (Enter trava, cadeado no slot de anotação; clicar destrava); a
// trava é gravada no mês e o resto redistribui pela API, com o total = planejado.
// Story 8.7: realizado e pendente por linha, o Andamento do mês (Barra de progresso) e o rodapé de
// conciliação — objetivos + classes · + na corretora, ainda não aplicado (sem classe) · = total do mês.
// Por lote (pedido de 18/10/2026): o plano de cada ativo da B3/Tesouro vem em unidades inteiras ao preço
// de hoje (o troco vai para a classe de valor livre); "O que falta aplicar" é a lista de compras — o que
// falta do plano, dentro do que falta na classe —, e cada linha mostra alocação × meta, preço, plano,
// realizado e falta, em R$ e em cotas.
import { ChevronRightIcon, LockIcon } from "lucide-react";
import Link from "next/link";
import { Fragment, type ReactNode, useState } from "react";

import { Input } from "@/components/ui/input";

import { ProgressBar } from "@/components/data/ProgressBar";
import { AllocationCell } from "@/components/investimentos/AllocationCell";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/button";
import { fmtQty, formatBRL, formatMonth, formatPercent, normalizeMoneyInput } from "@/lib/format";
import { useDistribution, useSetLock } from "@/lib/planning";
import { cn } from "@/lib/utils";
import type { Distribution, DistributionAsset, DistributionGoal } from "@/types/planning";

type Lock = (key: string, valor: string | null, onError?: () => void) => void;

const LOCK_FAILED = "Não foi possível salvar. Nada foi perdido. Tentar de novo.";

function LockCell({
  lockKey,
  label,
  value,
  locked,
  readOnly,
  busy,
  onLock,
}: {
  lockKey: string;
  label: string;
  value: number;
  locked: boolean;
  readOnly: boolean;
  busy: boolean;
  onLock: Lock;
}) {
  // O pai remonta a célula (key) quando o valor muda; com erro, a célula fica e mantém o digitado.
  const shown = value.toFixed(2).replace(".", ",");
  const [text, setText] = useState(shown);
  const [error, setError] = useState<string | null>(null);
  if (readOnly) return <span className="type-num-table">{formatBRL(value)}</span>;
  function commit() {
    const normalized = normalizeMoneyInput(text);
    if (normalized === null || Number(normalized) < 0) {
      setError("Informe um valor (ex.: 800,00).");
      return;
    }
    setError(null);
    onLock(lockKey, normalized, () => setError(LOCK_FAILED));
  }
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <span className="inline-flex items-center gap-1">
        {locked && (
          <button
            type="button"
            aria-label={`Destravar ${label}`}
            title="Destravar: volta ao sugerido"
            className="text-muted-foreground hover:text-foreground disabled:opacity-50"
            disabled={busy}
            onClick={() => onLock(lockKey, null, () => setError(LOCK_FAILED))}
          >
            <LockIcon aria-hidden className="size-3.5" />
          </button>
        )}
        <Input
          aria-label={`Sugerido para ${label}`}
          inputMode="decimal"
          value={text}
          readOnly={busy}
          aria-busy={busy}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (busy) return; // uma trava por vez: a prévia de uma não sobrescreve a outra
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setText(shown);
              setError(null);
            }
          }}
          aria-invalid={Boolean(error)}
          className="h-8 w-28 type-num-table text-right"
        />
      </span>
      {error && (
        <span role="alert" className="type-caption text-negative">
          {error}
        </span>
      )}
    </span>
  );
}

function goalNote(g: DistributionGoal): string {
  if (g.kind === "reserva") return g.monthly > 0 ? `${formatBRL(g.monthly)}/mês até encher` : "cheia";
  if (!g.deadline || g.monthly <= 0) return "alcançado";
  return `${formatBRL(g.monthly)}/mês para chegar em ${formatMonth(g.deadline.slice(0, 7))}`;
}

function Goals({
  data,
  readOnly,
  busy,
  onLock,
}: {
  data: Distribution;
  readOnly: boolean;
  busy: boolean;
  onLock: Lock;
}) {
  if (!data.goals.length) return null;
  return (
    <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card">
      <table className="w-full type-body-sm">
        <caption className="sr-only">Objetivos</caption>
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2 text-left font-medium">Objetivo</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Progresso</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Alvo</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Sugerido</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Realizado</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Pendente</th>
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
                <ProgressBar
                  label={`${g.name}: ${formatPercent(g.progress)} do alvo`}
                  solid={Math.min(g.progress, 100)}
                  className="mt-1 w-28"
                />
              </td>
              <td className="px-4 py-2 text-right type-num-table">{formatBRL(g.target)}</td>
              <td className="px-4 py-2 text-right">
                <LockCell
                  key={`${g.id}-${g.sugerido}-${g.locked}`}
                  lockKey={`goal:${g.id}`}
                  label={g.name}
                  value={g.sugerido}
                  locked={g.locked}
                  readOnly={readOnly}
                  busy={busy}
                  onLock={onLock}
                />
              </td>
              <td className="px-4 py-2 text-right type-num-table">{formatBRL(g.realizado)}</td>
              <td className="px-4 py-2 text-right type-num-table">{formatBRL(g.pendente)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Unidades em texto da API ("10", "0.03") → "10 cotas" · "0,03 título".
function unitsText(qty: string, unidade: DistributionAsset["unidade"]): string {
  const n = Number(qty);
  const shown = fmtQty(n);
  if (unidade === "título") return `${shown} título`;
  return `${shown} ${n === 1 ? "cota" : "cotas"}`;
}

function priceText(a: DistributionAsset): string | null {
  if (a.preco == null) return null;
  return `${formatBRL(Number(a.preco))}/${a.unidade === "título" ? "título" : "cota"}`;
}

// O que falta aplicar no mês (pedido de 18/10/2026): a lista de compras — objetivos e classes de valor
// livre em R$, ativos com lote em unidades inteiras × preço de hoje. Vem pronta da API.
function ToBuy({ data, periodo }: { data: Distribution; periodo: string }) {
  type Item = { key: string; what: string; how: string | null; value: number };
  const items: Item[] = [];
  for (const g of data.goals) {
    if (g.pendente > 0) items.push({ key: `goal:${g.id}`, what: g.name, how: "objetivo", value: g.pendente });
  }
  for (const c of data.classes) {
    const lotted = c.assets.filter((a) => a.comprar_cotas != null);
    if (lotted.length) {
      for (const a of lotted) {
        if (!a.comprar || !a.comprar_cotas) continue;
        items.push({
          key: `asset:${a.id}`,
          what: a.label,
          how: `${unitsText(a.comprar_cotas, a.unidade)} × ${formatBRL(Number(a.preco ?? 0))}`,
          value: a.comprar,
        });
      }
    } else if (c.comprar > 0) {
      items.push({ key: `class:${c.cls}`, what: c.label, how: "valor livre", value: c.comprar });
    }
  }
  const total = items.reduce((sum, i) => sum + i.value, 0);
  const leftover = data.classes.filter((c) => c.comprar_troco > 0);
  return (
    <section aria-labelledby="a-aplicar" className="space-y-2 rounded-lg border border-border bg-card shadow-card p-card-padding">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="a-aplicar" className="type-label">
          O que falta aplicar em {formatMonth(periodo)}
        </h3>
        {items.length > 0 && <span className="type-num-body">{formatBRL(total)}</span>}
      </div>
      {items.length === 0 ? (
        <p className="type-body-sm text-muted-foreground">Nada pendente: o plano do mês está aplicado.</p>
      ) : (
        <ul className="divide-y divide-border type-body-sm">
          {items.map((i) => (
            <li key={i.key} className="flex flex-wrap items-baseline justify-between gap-x-4 py-1.5">
              <span>
                <span className="font-medium type-num-table">{i.what}</span>
                {i.how && <span className="text-muted-foreground"> · {i.how}</span>}
              </span>
              <span className="type-num-table">{formatBRL(i.value)}</span>
            </li>
          ))}
        </ul>
      )}
      {leftover.length > 0 && (
        <p className="type-caption text-muted-foreground">
          {leftover.map((c) => `${formatBRL(c.comprar_troco)} de ${c.label}`).join(" · ")} não{" "}
          {leftover.length === 1 ? "compra" : "compram"} uma cota inteira agora: fica para o próximo aporte.
        </p>
      )}
    </section>
  );
}

function Classes({
  data,
  readOnly,
  busy,
  onLock,
}: {
  data: Distribution;
  readOnly: boolean;
  busy: boolean;
  onLock: Lock;
}) {
  // as classes com divisão por ativo começam abertas: o plano é por ativo
  const [open, setOpen] = useState<Set<string>>(
    () => new Set(data.classes.filter((c) => c.assets.some((a) => a.sugerido != null)).map((c) => c.cls)),
  );
  const toggle = (cls: string) =>
    setOpen((cur) => {
      const next = new Set(cur);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });
  const head = "px-3 py-2 text-right font-medium";
  const cell = "px-3 py-2 text-right type-num-table align-top";
  return (
    <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card">
      <table className="w-full type-body-sm">
        <caption className="sr-only">Classes e ativos</caption>
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2 text-left font-medium">Classe / ativo</th>
            <th scope="col" className={head}>Alocação × meta</th>
            <th scope="col" className={head}>Preço</th>
            <th scope="col" className={head}>Plano do mês</th>
            <th scope="col" className={head}>Realizado</th>
            <th scope="col" className={head}>Falta</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.classes.map((c) => {
            const withAssets = c.assets.some((a) => a.sugerido != null);
            return (
              <Fragment key={c.cls}>
                <tr className="font-semibold">
                  <th scope="row" className="px-4 py-2 text-left align-top">
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
                    {c.floor_only && (
                      <span className="ml-2">
                        <StatusBadge tooltip="acima da banda: só o piso">piso</StatusBadge>
                      </span>
                    )}
                  </th>
                  <td className={cn(cell, "font-normal")}>
                    <AllocationCell alocacao={c.atual} meta={c.meta} banda={c.banda} desvio={c.desvio} fora={c.out_of_band} />
                  </td>
                  <td className={cell} />
                  <td className={cell}>
                    <LockCell
                      key={`${c.cls}-${c.sugerido}-${c.locked}`}
                      lockKey={`class:${c.cls}`}
                      label={c.label}
                      value={c.sugerido}
                      locked={c.locked}
                      readOnly={readOnly}
                      busy={busy}
                      onLock={onLock}
                    />
                    {c.troco > 0 && (
                      <span className="block type-caption font-normal text-muted-foreground">
                        troco {formatBRL(c.troco)} → {data.troco_destino.join(", ") || "sem destino"}
                      </span>
                    )}
                    {c.recebido_troco > 0 && (
                      <span className="block type-caption font-normal text-muted-foreground">
                        + {formatBRL(c.recebido_troco)} de troco das cotas
                      </span>
                    )}
                  </td>
                  <td className={cell}>{formatBRL(c.realizado)}</td>
                  <td className={cell}>
                    <Falta pendente={c.pendente} comprar={c.comprar} />
                  </td>
                </tr>
                {open.has(c.cls) &&
                  c.assets.map((a) => (
                    <tr key={a.id} className="text-muted-foreground">
                      <th scope="row" className="py-1.5 pr-3 pl-10 text-left align-top font-normal">
                        <span className="type-num-table text-foreground">{a.label}</span>
                      </th>
                      <td className={cn(cell, "py-1.5")}>
                        <AllocationCell alocacao={a.atual} meta={a.meta} banda={null} desvio={null} fora={false} compact />
                      </td>
                      <td className={cn(cell, "py-1.5")}>{priceText(a) ?? "—"}</td>
                      <td className={cn(cell, "py-1.5")}>
                        {a.sugerido != null && (a.sugerido > 0 || a.locked) ? (
                          <>
                            <LockCell
                              key={`${a.id}-${a.sugerido}-${a.locked}`}
                              lockKey={`asset:${a.id}`}
                              label={a.label}
                              value={a.sugerido}
                              locked={a.locked}
                              readOnly={readOnly}
                              busy={busy}
                              onLock={onLock}
                            />
                            {a.cotas != null && Number(a.cotas) > 0 && (
                              <span className="block type-caption">{unitsText(a.cotas, a.unidade)}</span>
                            )}
                          </>
                        ) : a.sugerido != null && !readOnly ? (
                          <ZeroPlan label={a.label}>
                            <LockCell
                              lockKey={`asset:${a.id}`}
                              label={a.label}
                              value={0}
                              locked={false}
                              readOnly={readOnly}
                              busy={busy}
                              onLock={onLock}
                            />
                          </ZeroPlan>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className={cn(cell, "py-1.5")}>
                        {formatBRL(a.realizado)}
                        {a.cotas_realizadas != null && Number(a.cotas_realizadas) > 0 && (
                          <span className="block type-caption">{unitsText(a.cotas_realizadas, a.unidade)}</span>
                        )}
                      </td>
                      <td className={cn(cell, "py-1.5")}>
                        {a.comprar_cotas != null ? (
                          Number(a.comprar_cotas) > 0 ? (
                            <span className="text-foreground">
                              {unitsText(a.comprar_cotas, a.unidade)}
                              <span className="block type-caption text-muted-foreground">{formatBRL(a.comprar ?? 0)}</span>
                            </span>
                          ) : a.pendente != null && a.pendente < 0 ? (
                            <span className="type-caption">acima do plano {formatBRL(-a.pendente)}</span>
                          ) : (
                            "—"
                          )
                        ) : a.pendente != null && a.pendente !== 0 ? (
                          <Falta pendente={a.pendente} comprar={Math.max(a.pendente, 0)} />
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
              </Fragment>
            );
          })}
        </tbody>
        <Reconciliation data={data} />
      </table>
    </div>
  );
}

// Ativo sem nada no plano: "—", e um clique abre o campo para travar um valor nele (Story 8.6).
function ZeroPlan({ label, children }: { label: string; children: ReactNode }) {
  const [editing, setEditing] = useState(false);
  if (editing) return <>{children}</>;
  return (
    <button
      type="button"
      aria-label={`Definir um valor para ${label}`}
      title="Definir um valor (trava)"
      className="rounded px-2 text-muted-foreground hover:bg-muted hover:text-foreground"
      onClick={() => setEditing(true)}
    >
      —
    </button>
  );
}

// O que falta na linha: o a comprar (R$) ou, quando o realizado passou do plano, quanto passou.
function Falta({ pendente, comprar }: { pendente: number; comprar: number }) {
  if (pendente < 0) return <span className="type-caption font-normal text-muted-foreground">acima do plano {formatBRL(-pendente)}</span>;
  return <>{formatBRL(comprar)}</>;
}

// Rodapé de conciliação (Story 8.7): os números vêm prontos da API.
function Reconciliation({ data }: { data: Distribution }) {
  const a = data.andamento;
  const cell = "px-4 py-2 text-right type-num-table";
  return (
    <tfoot className="border-t border-foreground">
      <tr>
        <th scope="row" colSpan={3} className="px-4 py-2 text-left font-normal">
          Objetivos + classes · realizado em ativo
        </th>
        <td className={cell}>{formatBRL(a.sugerido_linhas)}</td>
        <td className={cell}>{formatBRL(a.em_ativo)}</td>
        <td className={cell}>{formatBRL(a.pendente_linhas)}</td>
      </tr>
      <tr className="text-muted-foreground">
        <th scope="row" colSpan={3} className="px-4 py-2 text-left font-normal">
          Na corretora, ainda não aplicado · sem classe
        </th>
        <td className={cell}>—</td>
        <td className={cell}>+{formatBRL(a.a_caminho)}</td>
        <td className={cell}>−{formatBRL(a.a_caminho)}</td>
      </tr>
      <tr className="font-semibold">
        <th scope="row" colSpan={3} className="px-4 py-2 text-left">
          Total do mês
        </th>
        <td className={cell}>{formatBRL(a.planned)}</td>
        <td className={cell}>{formatBRL(a.realizado)}</td>
        <td className={cell}>{formatBRL(a.pendente)}</td>
      </tr>
    </tfoot>
  );
}

function Andamento({ data, periodo }: { data: Distribution; periodo: string }) {
  const a = data.andamento;
  return (
    <section aria-labelledby="andamento" className="space-y-2 rounded-lg border border-border bg-card shadow-card p-card-padding">
      <h3 id="andamento" className="type-label">
        Andamento de {formatMonth(periodo)}
      </h3>
      <p className="type-body-sm">
        Realizado <span className="type-num-body">{formatBRL(a.realizado)}</span> · dos quais{" "}
        <span className="type-num-body">{formatBRL(a.a_caminho)}</span> na corretora, ainda não aplicados · pendente{" "}
        <span className="type-num-body">{formatBRL(a.pendente)}</span> de{" "}
        <span className="type-num-body">{formatBRL(a.planned)}</span>
        {a.pct_realizado != null && <> · {formatPercent(a.pct_realizado)} realizado</>}
      </p>
      <ProgressBar
        label={`Realizado em ativo ${formatPercent(a.pct_em_ativo)} e na corretora, não aplicado, ${formatPercent(a.pct_a_caminho)} do planejado`}
        solid={a.pct_em_ativo}
        hatched={a.pct_a_caminho}
        legend={{ realizado: formatBRL(a.em_ativo), aCaminho: formatBRL(a.a_caminho), pendente: formatBRL(a.pendente) }}
      />
    </section>
  );
}

// Linhas cujo sugerido mudou (o anúncio "Redistribuído: {n} linhas"), sem contar a editada.
function changedLines(before: Distribution, after: Distribution, edited: string): number {
  const values = (d: Distribution) =>
    new Map<string, number | null>([
      ...d.goals.map((g) => [`goal:${g.id}`, g.sugerido] as const),
      ...d.classes.map((c) => [`class:${c.cls}`, c.sugerido] as const),
      ...d.classes.flatMap((c) => c.assets.map((a) => [`asset:${a.id}`, a.sugerido] as const)),
    ]);
  const old = values(before);
  return [...values(after)].filter(([k, v]) => k !== edited && old.get(k) !== v).length;
}

export function DistributionTable({
  periodo,
  enabled,
  readOnly,
}: {
  periodo: string;
  enabled: boolean;
  readOnly: boolean;
}) {
  const query = useDistribution(periodo, enabled);
  const setLock = useSetLock(periodo);
  const [announce, setAnnounce] = useState("");
  if (!enabled) return null;
  if (query.isError && !query.data) {
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
  if (!data) return <div className="h-64 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />;
  const onLock: Lock = (key, valor, onError) =>
    setLock.mutate(
      { key, valor },
      {
        onSuccess: (next) => setAnnounce(`Redistribuído: ${changedLines(data, next, key)} linhas`),
        onError,
      },
    );
  return (
    <section aria-labelledby="distribuicao" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="distribuicao" className="type-section-title">
          Distribuição do aporte
        </h2>
        <span className="type-caption text-muted-foreground">total = aporte planejado · {formatBRL(data.planned)}</span>
      </div>
      <p role="status" aria-live="polite" className="sr-only">
        {announce}
      </p>
      {data.locks_over && (
        <p role="alert" className="type-body-sm text-negative">
          Travas somam {formatBRL(data.locks_total)}, acima do planejado.
        </p>
      )}
      <Andamento data={data} periodo={periodo} />
      {!readOnly && <ToBuy data={data} periodo={periodo} />}
      <Goals data={data} readOnly={readOnly} busy={setLock.isPending} onLock={onLock} />
      {data.has_targets ? (
        <>
          <Classes data={data} readOnly={readOnly} busy={setLock.isPending} onLock={onLock} />
          <p className="type-caption text-muted-foreground">
            Por linha, o realizado só conta quando o dinheiro vira ativo.
            {data.andamento.confere && (
              <>
                {" "}
                Σ pendente das linhas {formatBRL(data.andamento.pendente_linhas)} = pendente total{" "}
                {formatBRL(data.andamento.pendente)} + na corretora, ainda não aplicado, {formatBRL(data.andamento.a_caminho)}.
              </>
            )}
          </p>
          {data.floors_reduced && (
            <p className="type-body-sm text-muted-foreground">
              Os pisos somam mais do que sobra depois dos objetivos: foram reduzidos em proporção.
            </p>
          )}
        </>
      ) : (
        <p className="rounded-lg border border-border bg-card shadow-card p-card-padding type-body text-muted-foreground">
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
