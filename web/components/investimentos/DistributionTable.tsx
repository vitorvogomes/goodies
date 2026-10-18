"use client";

// Distribuição do aporte (Story 8.5 — FR-29, UX-DR38, DESIGN › allocation-distribution): os
// objetivos (progresso até o alvo, "Snow Trip · R$ 350/mês para chegar em jul/2027") e as classes
// recolhidas, expansíveis para ativos, com meta, atual, desvio (p.p.), banda e sugerido — tudo de
// `POST /api/v1/planning/distribution/preview` (o front não calcula). Pisos reduzidos → a nota.
// Story 8.6: o sugerido se edita (Enter trava, cadeado no slot de anotação; clicar destrava); a
// trava é gravada no mês e o resto redistribui pela API, com o total = planejado.
// Story 8.7: realizado e pendente por linha, o Andamento do mês (Barra de progresso) e o rodapé de
// conciliação — objetivos + classes · + a caminho, ainda sem classe · = total do mês.
import { ChevronRightIcon, LockIcon } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";

import { Input } from "@/components/ui/input";

import { ProgressBar } from "@/components/data/ProgressBar";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/button";
import { formatBRL, formatMonth, formatPercent, formatPP, normalizeMoneyInput } from "@/lib/format";
import { useDistribution, useSetLock } from "@/lib/planning";
import { cn } from "@/lib/utils";
import type { Distribution, DistributionGoal } from "@/types/planning";

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
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (cls: string) =>
    setOpen((cur) => {
      const next = new Set(cur);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });
  return (
    <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card">
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
            <th scope="col" className="px-4 py-2 text-right font-medium">Realizado</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Pendente</th>
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
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right type-num-table">{formatBRL(c.realizado)}</td>
                  <td className="px-4 py-2 text-right type-num-table">{formatBRL(c.pendente)}</td>
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
                      <td className="px-4 py-1.5 text-right">
                        {a.sugerido != null ? (
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
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-4 py-1.5 text-right type-num-table">{formatBRL(a.realizado)}</td>
                      <td className="px-4 py-1.5 text-right type-num-table">{a.pendente != null ? formatBRL(a.pendente) : "—"}</td>
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

// Rodapé de conciliação (Story 8.7): os números vêm prontos da API.
function Reconciliation({ data }: { data: Distribution }) {
  const a = data.andamento;
  const cell = "px-4 py-2 text-right type-num-table";
  return (
    <tfoot className="border-t border-foreground">
      <tr>
        <th scope="row" colSpan={5} className="px-4 py-2 text-left font-normal">
          Objetivos + classes · realizado em ativo
        </th>
        <td className={cell}>{formatBRL(a.sugerido_linhas)}</td>
        <td className={cell}>{formatBRL(a.em_ativo)}</td>
        <td className={cell}>{formatBRL(a.pendente_linhas)}</td>
      </tr>
      <tr className="text-muted-foreground">
        <th scope="row" colSpan={5} className="px-4 py-2 text-left font-normal">
          A caminho · ainda sem classe
        </th>
        <td className={cell}>—</td>
        <td className={cell}>+{formatBRL(a.a_caminho)}</td>
        <td className={cell}>−{formatBRL(a.a_caminho)}</td>
      </tr>
      <tr className="font-semibold">
        <th scope="row" colSpan={5} className="px-4 py-2 text-left">
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
        <span className="type-num-body">{formatBRL(a.a_caminho)}</span> a caminho · pendente{" "}
        <span className="type-num-body">{formatBRL(a.pendente)}</span> de{" "}
        <span className="type-num-body">{formatBRL(a.planned)}</span>
        {a.pct_realizado != null && <> · {formatPercent(a.pct_realizado)} realizado</>}
      </p>
      <ProgressBar
        label={`Realizado em ativo ${formatPercent(a.pct_em_ativo)} e a caminho ${formatPercent(a.pct_a_caminho)} do planejado`}
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
                {formatBRL(data.andamento.pendente)} + a caminho, ainda sem classe, {formatBRL(data.andamento.a_caminho)}.
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
