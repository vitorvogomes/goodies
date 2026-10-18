"use client";

// Caixa › Transações (Story 2.7 — FR-12, FR-16, UX-DR14, UX-DR31): transações do período com tipo,
// "Grupo › Subcategoria", origem da categoria, pagador e conta; a linha expandida mostra fonte,
// lote e regra aplicada; a categoria se corrige na linha (categorize, origem manual).
import { PlusIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { BalanceCandidates } from "@/components/caixa/BalanceCandidates";
import { CategoryCombobox } from "@/components/caixa/CategoryCombobox";
import { RuleProposalStrip } from "@/components/caixa/RuleProposalStrip";
import { TransactionForm } from "@/components/caixa/TransactionForm";
import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { StatusBadge } from "@/components/data/StatusBadge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/errors";
import { ApiError } from "@/lib/api";
import { formatBRL, formatDate, formatMonth } from "@/lib/format";
import {
  useCategoryOptions,
  useDeleteManualTransaction,
  useLedgerTransactions,
  useSetTransactionCategory,
} from "@/lib/ledger";
import { usePeriodo } from "@/lib/use-periodo";
import type { CategoryOption, LedgerTransaction } from "@/types/ledger";

const ORIGEM: Record<LedgerTransaction["category_source"], string> = {
  rule: "regra",
  suggestion: "sugestão",
  manual: "manual",
};
const FONTE: Record<string, string> = {
  nubank_ofx: "OFX do Nubank",
  nubank_csv: "CSV do Nubank",
  b3_movimentacao: "B3 · movimentação",
  b3_negociacao: "B3 · negociação",
  manual: "lançamento manual",
  hermes: "Hermes",
  derived: "derivada",
};
const EMPTY: LedgerTransaction[] = [];

// "Grupo › Subcategoria"; categoria de sistema (a classificar) aparece só pelo nome.
function categoryLabel(t: LedgerTransaction): string {
  return t.category_key.startsWith("sistema:") ? t.category_name : `${t.group_name} › ${t.category_name}`;
}
const NO_OPTIONS: CategoryOption[] = [];

function Transacoes() {
  const { periodo } = usePeriodo();
  // Ação "Ver transações" do aviso de saldo divergente: ?conferencia=<início>_<fim> (Story 3.13).
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [cStart, cEnd] = (params.get("conferencia") ?? "").split("_");
  const conferencia = cStart && cEnd ? { start: cStart, end: cEnd } : null;
  const closeConferencia = () => {
    const next = new URLSearchParams(params);
    next.delete("conferencia");
    router.replace(next.size ? `${pathname}?${next}` : pathname);
  };
  const txs = useLedgerTransactions(periodo);
  const options = useCategoryOptions();
  // Ação "Ver transações" do aviso de gasto acima da média: ?categoria=<id> (Story 6.4).
  const categoryFilter = params.get("categoria");
  const clearCategory = () => {
    const next = new URLSearchParams(params);
    next.delete("categoria");
    next.delete("grupo");
    router.replace(next.size ? `${pathname}?${next}` : pathname);
  };
  // Clique numa barra do gráfico de gastos do Histórico: ?grupo=<chave do grupo> (Story 9.3).
  const groupFilter = params.get("grupo");
  const groupCategories = new Set(
    (options.data ?? []).filter((o) => o.group_key === groupFilter).map((o) => o.id),
  );
  const shown = categoryFilter
    ? (txs.data?.items ?? EMPTY).filter((t) => t.category_id === categoryFilter)
    : groupFilter
      ? (txs.data?.items ?? EMPTY).filter((t) => groupCategories.has(t.category_id))
      : (txs.data?.items ?? EMPTY);
  const filterLabel = categoryFilter
    ? options.data?.find((o) => o.id === categoryFilter)?.label
    : options.data?.find((o) => o.group_key === groupFilter)?.group_name;
  const setCategory = useSetTransactionCategory();
  const remove = useDeleteManualTransaction();
  const [form, setForm] = useState<{ open: boolean; tx: LedgerTransaction | null }>({
    open: false,
    tx: null,
  });
  const [toDelete, setToDelete] = useState<LedgerTransaction | null>(null);
  // Categoria de regra/sugestão corrigida na linha: faixa "Criar regra?" sob ela (Story 3.11).
  const [proposal, setProposal] = useState<{ id: string; categoryId: string } | null>(null);

  const change = (tx: LedgerTransaction, option: CategoryOption) =>
    setCategory.mutate(
      { id: tx.id, categoryId: option.id },
      {
        onSuccess: () => {
          if (
            (tx.category_source === "rule" || tx.category_source === "suggestion") &&
            option.id !== tx.category_id
          ) {
            setProposal({ id: tx.id, categoryId: option.id });
          }
        },
        onError: (err) =>
          toast(
            err instanceof ApiError
              ? apiErrorMessage(err.detail, "Não foi possível salvar. Nada foi perdido.")
              : "Não foi possível salvar. Nada foi perdido.",
          ),
      },
    );

  const columns: DataColumn<LedgerTransaction>[] = [
    { id: "date", header: "Data", value: (t) => t.date, cell: (t) => formatDate(t.date), className: "type-num-table" },
    {
      id: "description",
      header: "Descrição",
      value: (t) => t.description,
      cell: (t) => <span className="block max-w-80 truncate">{t.description ?? "—"}</span>,
    },
    { id: "amount", header: "Valor", value: (t) => t.amount, cell: (t) => formatBRL(t.amount), numeric: true },
    { id: "kind", header: "Tipo", value: (t) => t.kind_label },
    {
      id: "category",
      header: "Categoria",
      value: categoryLabel,
      cell: (t) => (
        <CategoryCombobox
          options={options.data ?? NO_OPTIONS}
          value={t.category_id}
          label={categoryLabel(t)}
          empty={t.category_key.startsWith("sistema:")}
          disabled={setCategory.isPending && setCategory.variables?.id === t.id}
          onSelect={(o) => change(t, o)}
        />
      ),
    },
    {
      id: "origin",
      header: "Origem",
      value: (t) => ORIGEM[t.category_source],
      cell: (t) => (
        <span className="inline-flex gap-1">
          <StatusBadge>{ORIGEM[t.category_source]}</StatusBadge>
          {t.review_status === "pending" && <StatusBadge tone="warning">a revisar</StatusBadge>}
        </span>
      ),
    },
    { id: "payer", header: "Pagador", value: (t) => t.payer, detailOnly: true },
    { id: "account", header: "Conta", value: (t) => t.account_name, detailOnly: true },
  ];

  if (txs.isError) {
    return <p className="type-body text-negative">Não foi possível carregar as transações.</p>;
  }
  return (
    <div className="space-y-3">
      {conferencia && <BalanceCandidates range={conferencia} onClose={closeConferencia} />}
      {(categoryFilter || groupFilter) && (
        <p className="type-body-sm" role="status">
          Só {filterLabel ?? (groupFilter ? "o grupo" : "a categoria do aviso")} em {formatMonth(periodo)} ({shown.length}).{" "}
          <button type="button" className="text-positive underline" onClick={clearCategory}>
            Ver todas
          </button>
        </p>
      )}
      <div className="flex justify-end">
        <Button variant="secondary" onClick={() => setForm({ open: true, tx: null })}>
          <PlusIcon aria-hidden />
          Nova transação
        </Button>
      </div>
      {form.open && (
        <TransactionForm
          key={form.tx?.id ?? "nova"}
          open
          transaction={form.tx}
          options={options.data ?? NO_OPTIONS}
          onClose={() => setForm({ open: false, tx: null })}
        />
      )}
      <AlertDialog open={toDelete !== null} onOpenChange={(v) => (v ? undefined : setToDelete(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Apagar transação</AlertDialogTitle>
            <AlertDialogDescription>
              {toDelete &&
                `${formatBRL(toDelete.amount)} em ${formatDate(toDelete.date)} · ${toDelete.description ?? "sem descrição"}. Só lançamentos à mão podem ser apagados.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel autoFocus>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() =>
                toDelete &&
                remove.mutate(toDelete.id, {
                  onSuccess: () => toast("Transação apagada."),
                  onError: () => toast("Não foi possível apagar. Nada foi perdido."),
                })
              }
            >
              Apagar transação
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <DataTable
      tableId="caixa-transacoes"
      caption={`Transações de ${formatMonth(periodo)}`}
      data={shown}
      columns={columns}
      getRowId={(t) => t.id}
      empty={
        txs.isLoading
          ? "Carregando…"
          : `Nenhuma transação em ${formatMonth(periodo)}. Importe o extrato do Nubank.`
      }
      renderBelow={(t) =>
        proposal?.id === t.id ? (
          <RuleProposalStrip
            transactionId={t.id}
            categoryId={proposal.categoryId}
            onClose={() => setProposal(null)}
          />
        ) : null
      }
      renderExpanded={(t) => (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 type-body-sm">
          <dt className="text-muted-foreground">Fonte</dt>
          <dd>{FONTE[t.source] ?? t.source}</dd>
          <dt className="text-muted-foreground">Lote</dt>
          <dd>
            {t.batch_id ? (
              <>
                {t.file_name ?? "lote legado"}{" "}
                <span className="type-num-table text-muted-foreground">#{t.batch_id.slice(0, 8)}</span>
              </>
            ) : (
              "sem lote"
            )}
          </dd>
          <dt className="text-muted-foreground">Regra aplicada</dt>
          <dd>{t.rule_pattern ? `descrição contém “${t.rule_pattern}”` : "—"}</dd>
          <dt className="text-muted-foreground">Pagador</dt>
          <dd>{t.payer ?? "—"}</dd>
          <dt className="text-muted-foreground">Conta</dt>
          <dd>{t.account_name}</dd>
          {t.source === "manual" && (
            <>
              <dt className="sr-only">Ações</dt>
              <dd className="col-start-2 flex gap-4 pt-1">
                <button
                  type="button"
                  className="text-positive underline"
                  onClick={() => setForm({ open: true, tx: t })}
                >
                  Editar
                </button>
                <button type="button" className="text-negative underline" onClick={() => setToDelete(t)}>
                  Apagar
                </button>
              </dd>
            </>
          )}
        </dl>
      )}
    />
    </div>
  );
}

export default function TransacoesPage() {
  return (
    <Suspense>
      <Transacoes />
    </Suspense>
  );
}
