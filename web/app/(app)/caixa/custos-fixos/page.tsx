"use client";

// Caixa › Custos fixos (Story 6.2 — FR-18, UX-DR37): a Lista de custos fixos com casamento do mês.
// Ordem atrasado → pago; Selo de estado; a transação casada (±10%, −5 a +5 dias). Ações: Confirmar ·
// Trocar (transações do mês, com busca) · Marcar pago manualmente · Desfazer casamento. Duas
// candidatas: "pendente" + "2 candidatas" em opções sob a linha (borda de aviso), nada pago até
// escolher. Mês fechado: só leitura até reabrir. O casamento vem da API; a tela não calcula.
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { StatusBadge } from "@/components/data/StatusBadge";
import { SAVE_FAILED } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatBRL, formatDate, formatMonth, formatSignedBRL } from "@/lib/format";
import { useFixedCostDecision, useFixedCostMonth, useLedgerTransactions } from "@/lib/ledger";
import { usePeriodo } from "@/lib/use-periodo";
import type { FixedCostDecisionKind, FixedCostMonthItem, FixedCostTx } from "@/types/ledger";

function txLabel(t: FixedCostTx): string {
  return `${formatDate(t.date)} · ${t.description ?? "—"} · ${formatSignedBRL(t.amount)}`;
}

function TrocarPopover({
  periodo,
  onPick,
}: {
  periodo: string;
  onPick: (txId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const txs = useLedgerTransactions(periodo);
  const q = query.trim().toLowerCase();
  const items = (txs.data?.items ?? [])
    .filter((t) => t.amount < 0)
    .filter((t) => !q || (t.description ?? "").toLowerCase().includes(q))
    .slice(0, 50);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" className="text-positive underline">
          Trocar
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-96 space-y-2" align="end">
        <Input
          autoFocus
          aria-label="Buscar transação do mês"
          placeholder="Buscar transação do mês"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <ul className="max-h-64 space-y-0.5 overflow-y-auto type-body-sm" aria-label="Transações do mês">
          {txs.isLoading && <li className="text-muted-foreground">Carregando…</li>}
          {!txs.isLoading && items.length === 0 && <li className="text-muted-foreground">Nenhuma saída encontrada.</li>}
          {items.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                className="w-full rounded px-2 py-1 text-left hover:bg-row-highlight focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                onClick={() => {
                  setOpen(false);
                  onPick(t.id);
                }}
              >
                {txLabel(t)}
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

function Candidates({
  item,
  disabled,
  onConfirm,
}: {
  item: FixedCostMonthItem;
  disabled: boolean;
  onConfirm: (txId: string) => void;
}) {
  const [picked, setPicked] = useState<string | null>(null);
  const name = `candidatas-${item.id}`;
  return (
    <fieldset className="space-y-1.5 border-l-2 border-warning pl-3">
      <legend className="type-body-sm font-semibold">
        {item.candidates.length} candidatas para {item.name}. Escolha a transação certa.
      </legend>
      {item.candidates.map((t) => (
        <label key={t.id} className="flex items-center gap-2 type-body-sm">
          <input
            type="radio"
            name={name}
            value={t.id}
            disabled={disabled}
            checked={picked === t.id}
            onChange={() => setPicked(t.id)}
          />
          {txLabel(t)}
        </label>
      ))}
      <Button size="sm" disabled={disabled || picked === null} onClick={() => picked && onConfirm(picked)}>
        Confirmar
      </Button>
    </fieldset>
  );
}

const TONE: Record<FixedCostMonthItem["status"], "neutral" | "warning"> = {
  pago: "neutral",
  manual: "neutral",
  pendente: "neutral",
  vencendo: "warning",
  atrasado: "warning",
};

export default function CustosFixosMesPage() {
  const { periodo } = usePeriodo();
  const view = useFixedCostMonth(periodo);
  const decide = useFixedCostDecision();
  const readOnly = view.data?.closed ?? false;

  function act(item: FixedCostMonthItem, kind: FixedCostDecisionKind | "limpar", transactionId?: string) {
    decide.mutate(
      { costId: item.id, mes: periodo, kind, transactionId },
      {
        onSuccess: () =>
          toast(
            kind === "manual"
              ? `${item.name} marcado pago manualmente.`
              : kind === "desfeito" || kind === "limpar"
                ? `Casamento de ${item.name} desfeito.`
                : `${item.name} pago.`,
          ),
        onError: () => toast(`${SAVE_FAILED} Tentar de novo.`),
      },
    );
  }

  const columns: DataColumn<FixedCostMonthItem>[] = [
    { id: "custo", header: "Custo", value: (i) => i.name },
    { id: "valor", header: "Valor", value: (i) => i.amount, numeric: true, cell: (i) => formatBRL(i.amount) },
    { id: "vencimento", header: "Vencimento", value: (i) => i.due_date, cell: (i) => formatDate(i.due_date) },
    {
      id: "estado",
      header: "Estado",
      value: (i) => i.status,
      cell: (i) => (
        <span className="inline-flex items-center gap-2">
          <StatusBadge tone={TONE[i.status]}>{i.status}</StatusBadge>
          {i.candidates.length > 1 && (
            <span className="type-caption text-warning">{i.candidates.length} candidatas</span>
          )}
        </span>
      ),
    },
    {
      id: "transacao",
      header: "Transação casada",
      value: (i) => i.transaction?.description ?? null,
      cell: (i) =>
        i.transaction ? (
          <span className="type-body-sm">
            {txLabel(i.transaction)}
            {i.source === "auto" && <span className="text-muted-foreground"> · automático</span>}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      id: "acoes",
      header: "Ações",
      value: () => null,
      sortable: false,
      cell: (i) =>
        readOnly ? (
          <span className="type-caption text-muted-foreground">mês fechado</span>
        ) : (
          <span className="inline-flex flex-wrap gap-3">
            {i.transaction && i.source === "auto" && (
              <button type="button" className="text-positive underline" onClick={() => act(i, "confirmado", i.transaction?.id)}>
                Confirmar
              </button>
            )}
            {i.status !== "manual" && <TrocarPopover periodo={periodo} onPick={(tx) => act(i, "corrigido", tx)} />}
            {!i.transaction && i.status !== "manual" && (
              <button type="button" className="text-positive underline" onClick={() => act(i, "manual")}>
                Marcar pago manualmente
              </button>
            )}
            {i.transaction && (
              <button type="button" className="text-positive underline" onClick={() => act(i, "desfeito", i.transaction?.id)}>
                Desfazer casamento
              </button>
            )}
            {i.status === "manual" && (
              <button type="button" className="text-positive underline" onClick={() => act(i, "limpar")}>
                Desfazer casamento
              </button>
            )}
          </span>
        ),
    },
  ];

  if (view.isError) {
    return (
      <p className="type-body text-negative">
        Não foi possível carregar os custos fixos.{" "}
        <button type="button" className="underline" onClick={() => view.refetch()}>
          Tentar de novo
        </button>
      </p>
    );
  }
  const data = view.data;
  if (data && data.count === 0) {
    return (
      <p className="type-body text-muted-foreground">
        Nenhum custo fixo cadastrado.{" "}
        <Link href="/ajustes/custos-fixos" className="text-positive underline">
          Cadastre em Ajustes › Custos fixos.
        </Link>
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {data && (
        <p className="type-body" aria-live="polite">
          <span className="font-semibold">
            pago {formatBRL(data.paid_total)} de {formatBRL(data.total)}
          </span>
          <span className="text-muted-foreground">
            {" "}
            · {data.paid_count} {data.paid_count === 1 ? "pago" : "pagos"} · {data.count - data.paid_count}{" "}
            {data.count - data.paid_count === 1 ? "pendente" : "pendentes"} ({formatBRL(data.pending_total)})
          </span>
          {readOnly && (
            <span className="text-muted-foreground"> · {formatMonth(periodo)} fechado: só leitura até reabrir.</span>
          )}
        </p>
      )}
      <DataTable
        tableId="caixa-custos-fixos"
        caption={`Custos fixos de ${formatMonth(periodo)}`}
        data={data?.items ?? []}
        columns={columns}
        getRowId={(i) => i.id}
        empty={view.isLoading ? "Carregando…" : "Nenhum custo fixo neste mês."}
        renderBelow={(i) =>
          i.candidates.length > 1 ? (
            <Candidates item={i} disabled={readOnly || decide.isPending} onConfirm={(tx) => act(i, "confirmado", tx)} />
          ) : null
        }
      />
    </div>
  );
}
