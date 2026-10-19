"use client";

// Conta do orçamento (Story 6.6 — DESIGN › budget-ledger, EXPERIENCE › Conta do orçamento): conta
// vertical com o operador em coluna própria; valores da API (AD-4). Receita do trabalho expande por
// pagador; Dívidas do mês é input inline (Enter grava, Esc reverte, anuncia o disponível novo);
// disponível ou restante negativo em vermelho com "−" e ▼ e a nota; abaixo, o consumo financiado
// por resgate (dividido em por objetivo × por resgate da carteira — Story 8.1) e o restante sem os
// resgates. Abaixo, o aporte planejado × realizado e as receitas esperadas (Ajustes ›
// Custos e receitas) × recebidas; o que falta receber dá um disponível à parte (a conta não muda).
import { type ReactNode, useState } from "react";

import { TrendArrow } from "@/components/data/TrendArrow";
import { Input } from "@/components/ui/input";
import { formatBRL, formatDate, normalizeMoneyInput } from "@/lib/format";
import { useSetDividas } from "@/lib/planning";
import { cn } from "@/lib/utils";
import type { Valued } from "@/types/overview";
import type { MonthBudget } from "@/types/planning";

const SAVE_FAILED = "Não foi possível salvar as dívidas. Nada foi perdido. Tentar de novo.";

const INCOME_STATUS: Record<MonthBudget["receitas_planejadas"][number]["status"], string> = {
  recebido: "recebido",
  parcial: "parcial",
  a_receber: "a receber",
  atrasado: "atrasado",
};

function money(v: Valued | number): string {
  const value = typeof v === "number" ? v : v.value;
  return value === null ? "—" : formatBRL(value);
}

function Row({
  op,
  label,
  value,
  total = false,
  negative = false,
  children,
}: {
  op: "+" | "−" | "=";
  label: ReactNode;
  value: ReactNode;
  total?: boolean;
  negative?: boolean;
  children?: ReactNode;
}) {
  return (
    <tr className={cn(total && "border-t border-foreground")}>
      <td className="w-6 py-2 pr-2 align-top type-num-body text-muted-foreground" aria-hidden>
        {op}
      </td>
      <th scope="row" className="py-2 pr-4 text-left align-top font-normal">
        <span className={cn(total && "font-semibold")}>{label}</span>
        {children && <div className="type-caption text-muted-foreground">{children}</div>}
      </th>
      <td
        className={cn(
          "py-2 text-right align-top",
          total ? "type-num-lg" : "type-num-body",
          negative && "text-negative",
        )}
      >
        {negative && <TrendArrow up={false} />}
        {value}
      </td>
    </tr>
  );
}

function DividasInput({
  budget,
  saving,
  onCommit,
}: {
  budget: MonthBudget;
  saving: boolean;
  onCommit: (valor: string | null, onError: () => void) => void;
}) {
  // O pai remonta o campo (key) quando o valor gravado muda: volta ao que a API devolveu. A mutação
  // fica no pai: o campo remontado não receberia o retorno dela.
  const shown = budget.dividas.toFixed(2).replace(".", ",");
  const [value, setValue] = useState(shown);
  const [error, setError] = useState<string | null>(null);

  function commit() {
    const raw = value.trim();
    const normalized = raw === "" ? null : normalizeMoneyInput(raw);
    if (raw !== "" && (normalized === null || Number(normalized) < 0)) {
      setError("Informe um valor (ex.: 650,00) ou deixe vazio para usar o calculado.");
      return;
    }
    setError(null);
    onCommit(normalized, () => setError(SAVE_FAILED));
  }

  const legend = budget.dividas_informadas
    ? "valor que você informa · Enter grava, Esc reverte"
    : budget.dividas_prefill > 0
      ? "calculado das transações em Dívidas"
      : "sem dívidas informadas";
  return (
    <span className="inline-flex flex-col items-end gap-1">
      {budget.closed ? (
        <span className="type-num-body">{budget.detalhe ? formatBRL(budget.dividas) : "—"}</span>
      ) : (
        <Input
          aria-label="Dívidas do mês"
          aria-describedby="dividas-legenda"
          inputMode="decimal"
          value={value}
          disabled={saving}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setValue(shown);
              setError(null);
            }
          }}
          className="h-8 w-36 type-num-body text-right"
          aria-invalid={Boolean(error)}
        />
      )}
      <span id="dividas-legenda" className="type-caption text-muted-foreground">
        {budget.closed ? "mês fechado: só leitura" : legend}
      </span>
      {error && (
        <span role="alert" className="type-caption text-negative">
          {error}
        </span>
      )}
    </span>
  );
}

// Receitas esperadas do mês × recebidas: o que falta receber soma num disponível à parte.
function PlannedIncomes({ budget }: { budget: MonthBudget }) {
  const comAReceber = budget.disponivel_com_a_receber.value;
  return (
    <div className="space-y-1 border-t border-border pt-3 type-body-sm">
      <table className="w-full">
        <caption className="pb-1 text-left font-semibold">Receitas planejadas</caption>
        <thead className="text-muted-foreground">
          <tr>
            <th scope="col" className="py-1 text-left font-normal">Receita</th>
            <th scope="col" className="py-1 text-right font-normal">Planejado</th>
            <th scope="col" className="py-1 text-right font-normal">Recebido</th>
            <th scope="col" className="py-1 text-right font-normal">Estado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {budget.receitas_planejadas.map((i) => (
            <tr key={i.id}>
              <th scope="row" className="py-1 text-left font-normal">
                {i.name}
                <span className="block type-caption text-muted-foreground">
                  {i.payer ? `${i.payer} · ` : ""}dia {formatDate(i.due_date).slice(0, 5)}
                </span>
              </th>
              <td className="py-1 text-right type-num-table">{formatBRL(i.amount)}</td>
              <td className="py-1 text-right type-num-table">{formatBRL(i.received)}</td>
              <td className={cn("py-1 text-right", i.status === "atrasado" && "text-warning")}>
                {INCOME_STATUS[i.status]}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="flex justify-between gap-4">
        <span>
          Disponível se receber o que falta{" "}
          <span className="text-muted-foreground">· + {formatBRL(budget.receita_a_receber)} a receber</span>
        </span>
        <span className={cn("type-num-body", comAReceber !== null && comAReceber < 0 && "text-negative")}>
          {money(budget.disponivel_com_a_receber)}
        </span>
      </p>
    </div>
  );
}

export function BudgetLedger({ budget, periodo }: { budget: MonthBudget; periodo: string }) {
  const [payers, setPayers] = useState(false);
  // Depois de gravar as dívidas, anuncia o disponível recalculado pela API.
  const [saved, setSaved] = useState(false);
  const save = useSetDividas();
  const disponivel = budget.disponivel.value;
  const restante = budget.restante.value;
  // Mês fechado antes do orçamento existir: só os totais congelados; os componentes não existiam.
  const part = (v: number) => (budget.detalhe ? formatBRL(v) : "—");
  return (
    <div className="space-y-section-gap">
      {!budget.detalhe && (
        <p className="type-body-sm text-muted-foreground">
          Mês fechado antes do orçamento: só os totais congelados. Reabra o mês (ou rode o refechar) para
          incluir o detalhe.
        </p>
      )}
      <table className="w-full type-body">
        <caption className="sr-only">Conta do orçamento</caption>
        <tbody>
          <Row
            op="+"
            label={
              budget.trabalho_por_pagador.length > 1 ? (
                <button
                  type="button"
                  aria-expanded={payers}
                  className="underline decoration-dotted underline-offset-4"
                  onClick={() => setPayers((v) => !v)}
                >
                  Receita do trabalho
                </button>
              ) : (
                "Receita do trabalho"
              )
            }
            value={money(budget.trabalho)}
          >
            {budget.receitas_planejadas.length > 0 && (
              <span className="block">
                planejado {formatBRL(budget.receita_planejada)} · a receber {formatBRL(budget.receita_a_receber)}
              </span>
            )}
            {payers &&
              budget.trabalho_por_pagador.map((p) => (
                <span key={p.payer} className="flex justify-between gap-4">
                  <span>{p.payer}</span>
                  <span className="type-num-table">{formatBRL(p.value)}</span>
                </span>
              ))}
          </Row>
          <Row op="+" label="Resgates" value={money(budget.resgates)}>
            {budget.resgates_itens
              .map((r) => `${r.description} · ${formatDate(r.date)}${r.goal ? ` · objetivo ${r.goal}` : ""}`)
              .join("; ")}
          </Row>
          <Row op="−" label="Custos fixos" value={money(budget.custos_fixos)}>
            {budget.detalhe &&
              `todos os do mês: pago ${formatBRL(budget.custos_fixos_pagos)} · a pagar ${formatBRL(budget.custos_fixos_a_pagar)}`}
          </Row>
          <Row op="−" label="Aporte planejado" value={part(budget.aporte_planejado)}>
            {budget.detalhe && !budget.aporte_definido
              ? `não definido · realizado ${formatBRL(budget.investido)}`
              : budget.detalhe && budget.aporte_diferenca !== null
                ? `realizado ${formatBRL(budget.investido)} · ${
                    budget.aporte_diferenca >= 0
                      ? `falta aportar ${formatBRL(budget.aporte_diferenca)}`
                      : `passou do planejado em ${formatBRL(-budget.aporte_diferenca)}`
                  }`
                : null}
          </Row>
          <Row
            op="−"
            label="Dívidas do mês"
            value={
              <DividasInput
                key={`${budget.dividas}-${budget.dividas_informadas}`}
                budget={budget}
                saving={save.isPending}
                onCommit={(valor, onError) =>
                  save.mutate({ periodo, valor }, { onSuccess: () => setSaved(true), onError })
                }
              />
            }
          />
          <Row
            op="="
            label="Disponível para consumo"
            value={money(budget.disponivel)}
            total
            negative={disponivel !== null && disponivel < 0}
          >
            {disponivel !== null &&
              disponivel < 0 &&
              `O planejado passa da receita em ${formatBRL(-disponivel)}. Reduza o aporte ou as dívidas.`}
          </Row>
          <Row op="−" label="Consumido" value={money(budget.consumido)}>
            {budget.detalhe && (
              <>
                gastos do mês sem os custos fixos: {formatBRL(budget.gastos)} − {formatBRL(budget.deducao_fixos)} pagos
                {budget.deducao_dividas > 0 && ` − ${formatBRL(budget.deducao_dividas)} em dívidas`}
                {budget.devolucoes > 0 && ` − ${formatBRL(budget.devolucoes)} de devoluções`}
              </>
            )}
          </Row>
          <Row
            op="="
            label="Restante"
            value={money(budget.restante)}
            total
            negative={restante !== null && restante < 0}
          >
            {restante !== null && restante < 0 && `Gasto acima do disponível em ${formatBRL(-restante)}.`}
          </Row>
        </tbody>
      </table>
      {budget.receitas_planejadas.length > 0 && <PlannedIncomes budget={budget} />}
      <p className="sr-only" role="status" aria-live="polite">
        {saved && disponivel !== null ? `Disponível: ${formatBRL(disponivel)}` : ""}
      </p>
      <div className="space-y-1 border-t border-border pt-3 type-body-sm">
        <p className="flex justify-between gap-4">
          <span>
            Consumo financiado por resgate{" "}
            <span className="text-muted-foreground">· coberto por resgates, não pelo trabalho</span>
          </span>
          <span className="type-num-body">{money(budget.consumo_financiado)}</span>
        </p>
        {(budget.consumo_financiado.value ?? 0) > 0 && budget.financiado_objetivo.value !== null && (
          <>
            {/* Story 8.1: o que o objetivo cobre (neutro) × o que saiu da carteira (laranja) */}
            <p className="flex justify-between gap-4 pl-4">
              <span>financiado por objetivo</span>
              <span className="type-num-body">{money(budget.financiado_objetivo)}</span>
            </p>
            <p className="flex justify-between gap-4 pl-4 text-warning">
              <span>financiado por resgate da carteira</span>
              <span className="type-num-body">{money(budget.financiado_carteira)}</span>
            </p>
          </>
        )}
        <p className="flex justify-between gap-4 text-muted-foreground">
          <span>Restante sem os resgates</span>
          <span className="type-num-body">{money(budget.restante_sem_resgates)}</span>
        </p>
      </div>
    </div>
  );
}
