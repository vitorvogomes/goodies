"use client";

// Caixa › Transações (Story 2.7 — FR-12, FR-16, UX-DR14, UX-DR31): transações do período com tipo,
// "Grupo › Subcategoria", origem da categoria, pagador e conta; a linha expandida mostra fonte,
// lote e regra aplicada; a categoria se corrige na linha (categorize, origem manual). Filtros por
// trecho da descrição, tipo, categoria, origem e pagador (como Operações); descrição, pagador e a
// condição da regra se editam na linha expandida (pedido de 18/10/2026). Linhas selecionáveis com a
// soma das selecionadas numa barra fixa (clique, Shift+clique, X, Ctrl/⌘+A, Esc limpa).
import { PlusIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
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
import { Input } from "@/components/ui/input";
import { useDebounced } from "@/lib/use-debounced";
import { apiErrorMessage } from "@/lib/errors";
import { ApiError } from "@/lib/api";
import { formatBRL, formatDate, formatMonth } from "@/lib/format";
import {
  CAIXINHA_RAIL,
  useCaixinhas,
  useCategoryOptions,
  useDeleteManualTransaction,
  useLedgerTransactions,
  useSaveManualTransaction,
  useSetCaixinha,
  useSetTransactionCategory,
  useUpdateRule,
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

// Texto editável na linha expandida: Enter grava, Esc volta ao gravado. `allowEmpty` limpa o campo.
function InlineText({
  label,
  initial,
  saving,
  onSave,
  allowEmpty = false,
  list,
  className = "h-8 w-full max-w-xl",
}: {
  label: string;
  initial: string;
  saving: boolean;
  onSave: (text: string) => void;
  allowEmpty?: boolean;
  list?: string;
  className?: string;
}) {
  const [text, setText] = useState(initial);
  return (
    <Input
      aria-label={label}
      value={text}
      list={list}
      readOnly={saving}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => {
        e.stopPropagation();
        const next = text.trim();
        if (e.key === "Enter" && (next || allowEmpty) && next !== initial) onSave(next);
        if (e.key === "Escape") setText(initial);
      }}
      className={className}
    />
  );
}

interface Filters {
  q: string;
  kind: string;
  category: string;
  origin: string;
  payer: string;
}
const NO_FILTERS: Filters = { q: "", kind: "", category: "", origin: "", payer: "" };
const SELECT = "h-9 w-full rounded-md border border-input bg-background px-2 type-body-sm text-foreground";

function normalize(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

function matches(t: LedgerTransaction, f: Filters, q: string): boolean {
  if (q && !normalize(t.description ?? "").includes(q)) return false;
  if (f.kind && t.kind_label !== f.kind) return false;
  if (f.category && t.category_id !== f.category) return false;
  if (f.origin === "pending" ? t.review_status !== "pending" : f.origin && t.category_source !== f.origin) return false;
  if (f.payer && (t.payer ?? "sem pagador") !== f.payer) return false;
  return true;
}

function FilterBar({
  items,
  filters,
  onChange,
}: {
  items: LedgerTransaction[];
  filters: Filters;
  onChange: (f: Filters) => void;
}) {
  const set = (key: keyof Filters) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange({ ...filters, [key]: e.target.value });
  const kinds = [...new Set(items.map((t) => t.kind_label))].sort();
  const categories = [...new Map(items.map((t) => [t.category_id, categoryLabel(t)])).entries()].sort((a, b) =>
    a[1].localeCompare(b[1], "pt-BR"),
  );
  const payers = [...new Set(items.map((t) => t.payer ?? "sem pagador"))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  const field = "space-y-1 type-caption text-muted-foreground";
  return (
    <div className="grid gap-card-gap sm:grid-cols-2 lg:grid-cols-5">
      <label className={field}>
        Descrição
        <Input value={filters.q} placeholder="busca por trecho: mercado, pix…" onChange={set("q")} />
      </label>
      <label className={field}>
        Tipo
        <select value={filters.kind} onChange={set("kind")} className={SELECT}>
          <option value="">Todos</option>
          {kinds.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
      </label>
      <label className={field}>
        Categoria
        <select value={filters.category} onChange={set("category")} className={SELECT}>
          <option value="">Todas</option>
          {categories.map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className={field}>
        Origem
        <select value={filters.origin} onChange={set("origin")} className={SELECT}>
          <option value="">Todas</option>
          <option value="rule">regra</option>
          <option value="suggestion">sugestão</option>
          <option value="manual">manual</option>
          <option value="pending">a revisar</option>
        </select>
      </label>
      <label className={field}>
        Pagador
        <select value={filters.payer} onChange={set("payer")} className={SELECT}>
          <option value="">Todos</option>
          {payers.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

// Barra fixa com a soma das linhas selecionadas (pedido de 18/10/2026).
function SelectionBar({ items, onClear }: { items: LedgerTransaction[]; onClear: () => void }) {
  if (items.length === 0) return null;
  const entradas = items.filter((t) => t.amount > 0).reduce((n, t) => n + t.amount, 0);
  const saidas = items.filter((t) => t.amount < 0).reduce((n, t) => n + t.amount, 0);
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 left-1/2 z-40 flex -translate-x-1/2 flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-border bg-card px-4 py-2 type-body-sm shadow-card"
    >
      <span className="font-semibold">
        {items.length} {items.length === 1 ? "selecionada" : "selecionadas"}
      </span>
      <span>
        entradas <span className="type-num-table text-positive">{formatBRL(entradas)}</span>
      </span>
      <span>
        saídas <span className="type-num-table text-negative">{formatBRL(saidas)}</span>
      </span>
      <span>
        saldo <span className="type-num-table font-semibold">{formatBRL(entradas + saidas)}</span>
      </span>
      <button type="button" className="text-positive underline" onClick={onClear}>
        Limpar (Esc)
      </button>
      <span className="type-caption text-muted-foreground">Shift+clique: intervalo · X: marcar · Ctrl/⌘+A: todas</span>
    </div>
  );
}

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
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  // Esc limpa a seleção de qualquer lugar da página (menos de dentro de um campo)
  useEffect(() => {
    if (selected.size === 0) return;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.key === "Escape" && !el?.closest("input, textarea, select, [role=dialog]")) setSelected(new Set());
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected.size]);
  const q = normalize(useDebounced(filters.q.trim()));
  const linked = categoryFilter
    ? (txs.data?.items ?? EMPTY).filter((t) => t.category_id === categoryFilter)
    : groupFilter
      ? (txs.data?.items ?? EMPTY).filter((t) => groupCategories.has(t.category_id))
      : (txs.data?.items ?? EMPTY);
  const shown = linked.filter((t) => matches(t, filters, q));
  const payerOptions = [...new Set((txs.data?.items ?? EMPTY).map((t) => t.payer).filter(Boolean))] as string[];
  const filterLabel = categoryFilter
    ? options.data?.find((o) => o.id === categoryFilter)?.label
    : options.data?.find((o) => o.group_key === groupFilter)?.group_name;
  const setCategory = useSetTransactionCategory();
  const remove = useDeleteManualTransaction();
  // O OFX não traz mais o nome da caixinha (desde 19/06/2026): escolhida na linha expandida.
  const caixinhas = useCaixinhas();
  const setCaixinha = useSetCaixinha();
  const saveTx = useSaveManualTransaction();
  const saveField = (t: LedgerTransaction, body: { description?: string; payer?: string }) =>
    saveTx.mutate(
      { id: t.id, body },
      {
        onSuccess: () => toast(body.payer !== undefined ? "Pagador salvo." : "Descrição salva."),
        onError: (err) =>
          toast(
            err instanceof ApiError
              ? apiErrorMessage(err.detail, "Não foi possível salvar. Nada foi perdido.")
              : "Não foi possível salvar. Nada foi perdido.",
          ),
      },
    );
  const caixinhaOf = (t: LedgerTransaction) =>
    t.category_key === "transfer:saldo_separado"
      ? "separado"
      : (caixinhas.data?.find((o) => o.asset_id && o.asset_id === t.asset_id)?.key ?? "");
  const chooseCaixinha = (t: LedgerTransaction, caixinha: string) =>
    setCaixinha.mutate(
      { id: t.id, caixinha },
      {
        onSuccess: (o) => toast(`Caixinha: ${o.label}.`),
        onError: (err) =>
          toast(
            err instanceof ApiError
              ? apiErrorMessage(err.detail, "Não foi possível salvar. Nada foi perdido.")
              : "Não foi possível salvar. Nada foi perdido.",
          ),
      },
    );
  const updateRule = useUpdateRule();
  const saveRule = (ruleId: string, pattern: string) =>
    updateRule.mutate(
      { id: ruleId, body: { pattern } },
      {
        onSuccess: () => toast("Regra salva. Vale para as próximas transações; reaplique em Ajustes › Regras."),
        onError: (err) =>
          toast(
            err instanceof ApiError
              ? apiErrorMessage(err.detail, "Não foi possível salvar. Nada foi perdido.")
              : "Não foi possível salvar. Nada foi perdido.",
          ),
      },
    );
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
      cell: (t) => <span className="line-clamp-2 block max-w-96">{t.description ?? "—"}</span>,
      priority: 1,
    },
    { id: "amount", header: "Valor", value: (t) => t.amount, cell: (t) => formatBRL(t.amount), numeric: true, priority: 1 },
    { id: "kind", header: "Tipo", value: (t) => t.kind_label, priority: 3 },
    {
      id: "category",
      header: "Categoria",
      value: categoryLabel,
      priority: 1,
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
      priority: 3,
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
      <FilterBar items={linked} filters={filters} onChange={setFilters} />
      <div className="flex items-center justify-between gap-2">
        <p className="type-caption text-muted-foreground" aria-live="polite">
          {shown.length === linked.length
            ? `${linked.length} transações`
            : `${shown.length} de ${linked.length} transações`}
          {Object.values(filters).some(Boolean) && (
            <>
              {" · "}
              <button type="button" className="text-positive underline" onClick={() => setFilters(NO_FILTERS)}>
                Limpar filtros
              </button>
            </>
          )}
        </p>
        <Button variant="secondary" onClick={() => setForm({ open: true, tx: null })}>
          <PlusIcon aria-hidden />
          Nova transação
        </Button>
      </div>
      <datalist id="pagadores">
        {payerOptions.map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>
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
      <SelectionBar
        items={shown.filter((t) => selected.has(t.id))}
        onClear={() => setSelected(new Set())}
      />
      <DataTable
      tableId="caixa-transacoes"
      filterable={false}
      selection={{ selected, onChange: setSelected }}
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
          <dt className="text-muted-foreground">Descrição</dt>
          <dd>
            <InlineText
              key={`${t.id}:${t.description ?? ""}`}
              label="Descrição"
              initial={t.description ?? ""}
              saving={saveTx.isPending}
              onSave={(description) => saveField(t, { description })}
            />
          </dd>
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
          {CAIXINHA_RAIL.includes(t.category_key) && (
            <>
              <dt className="text-muted-foreground">
                <label htmlFor={`caixinha-${t.id}`}>Caixinha</label>
              </dt>
              <dd>
                <select
                  id={`caixinha-${t.id}`}
                  value={caixinhaOf(t)}
                  disabled={setCaixinha.isPending || !caixinhas.data}
                  onChange={(e) => e.target.value && chooseCaixinha(t, e.target.value)}
                  className="h-8 rounded-md border border-input bg-background px-2 type-body-sm"
                >
                  {caixinhaOf(t) === "" && <option value="">a escolher (o extrato não diz)</option>}
                  {(caixinhas.data ?? []).map((o) => (
                    <option key={o.key} value={o.key}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </dd>
            </>
          )}
          <dt className="text-muted-foreground">Regra aplicada</dt>
          <dd>
            {t.rule_id && t.rule_pattern ? (
              <span className="flex flex-wrap items-center gap-2">
                descrição contém
                <InlineText
                  key={`${t.rule_id}:${t.rule_pattern}`}
                  label="Condição da regra"
                  initial={t.rule_pattern}
                  saving={updateRule.isPending}
                  onSave={(pattern) => saveRule(t.rule_id!, pattern)}
                  className="h-8 w-56"
                />
                <span className="type-caption text-muted-foreground">Enter grava (vale para toda a regra)</span>
              </span>
            ) : (
              <span className="flex flex-wrap items-center gap-2">
                —
                {!t.category_key.startsWith("sistema:") && t.description && (
                  <button
                    type="button"
                    className="text-positive underline"
                    onClick={() => setProposal({ id: t.id, categoryId: t.category_id })}
                  >
                    Criar regra com esta categoria
                  </button>
                )}
              </span>
            )}
          </dd>
          <dt className="text-muted-foreground">Pagador</dt>
          <dd>
            <InlineText
              key={`${t.id}:${t.payer ?? ""}`}
              label="Pagador"
              initial={t.payer ?? ""}
              saving={saveTx.isPending}
              allowEmpty
              list="pagadores"
              onSave={(payer) => saveField(t, { payer })}
              className="h-8 w-56"
            />
          </dd>
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
