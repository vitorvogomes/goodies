"use client";

// STORY-01-10 (+ adendo 3) — lista de transações: filtros + paginação, edição
// inline de descrição/categoria e totais (receita/despesa) do conjunto filtrado.
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button, Field, Input, Select } from "@/components/ui";
import { formatBRL, formatDate } from "@/lib/format";
import {
  useAccounts,
  useCategories,
  useTransactions,
  useUpdateTransaction,
} from "@/lib/ledger";
import type { CategoryKind, Transaction, TransactionCreate } from "@/types/ledger";

const LIMIT = 50;

// Cor do valor pelo tipo (não pelo sinal): investimento/transferência não são "perda".
const KIND_COLOR: Record<CategoryKind, string> = {
  income: "text-gain",
  expense: "text-loss",
  investment: "text-accent",
  transfer: "text-foreground/50",
};

function TransactionRow({
  tx,
  accountName,
  categoryNames,
  onSave,
}: {
  tx: Transaction;
  accountName: (id: string) => string;
  categoryNames: string[];
  onSave: (id: string, patch: Partial<TransactionCreate>) => void;
}) {
  const [editingDesc, setEditingDesc] = useState(false);
  const [descDraft, setDescDraft] = useState(tx.description ?? "");

  function commitDesc() {
    setEditingDesc(false);
    const value = descDraft.trim();
    if (value !== (tx.description ?? "")) onSave(tx.id, { description: value });
  }

  // garante a categoria atual selecionável mesmo se não estiver na lista ativa
  const options = categoryNames.includes(tx.category)
    ? categoryNames
    : [tx.category, ...categoryNames];

  return (
    <tr className="border-t border-border">
      <td className="px-4 py-2.5 tabular-nums text-foreground/80">{formatDate(tx.date)}</td>
      <td className="px-4 py-2.5 text-foreground/80">
        {editingDesc ? (
          <input
            autoFocus
            value={descDraft}
            onChange={(e) => setDescDraft(e.target.value)}
            onBlur={commitDesc}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitDesc();
              if (e.key === "Escape") {
                setDescDraft(tx.description ?? "");
                setEditingDesc(false);
              }
            }}
            className="w-full rounded border border-accent/40 bg-background px-1.5 py-1 text-foreground outline-none"
          />
        ) : (
          <button
            type="button"
            onClick={() => {
              setDescDraft(tx.description ?? "");
              setEditingDesc(true);
            }}
            className="block w-full cursor-text text-left hover:text-foreground"
          >
            {tx.description ?? "—"}
          </button>
        )}
        {!editingDesc && tx.notes && (
          <span className="mt-0.5 block text-xs italic text-foreground/40">{tx.notes}</span>
        )}
      </td>
      <td className="px-4 py-2.5">
        <select
          value={tx.category}
          onChange={(e) => onSave(tx.id, { category: e.target.value })}
          className="cursor-pointer rounded-lg border border-border bg-background px-2 py-1 text-foreground/80 outline-none transition hover:border-accent/40 focus:border-accent focus:ring-2 focus:ring-accent/40"
        >
          {options.map((name) => (
            <option key={name} value={name} className="bg-background text-foreground">
              {name}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-2.5 text-foreground/60">{accountName(tx.account_id)}</td>
      <td className={`px-4 py-2.5 text-right tabular-nums ${KIND_COLOR[tx.kind]}`}>
        {formatBRL(tx.amount)}
      </td>
    </tr>
  );
}

export default function LedgerPage() {
  const [accountId, setAccountId] = useState("");
  const [category, setCategory] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [offset, setOffset] = useState(0);

  const accounts = useAccounts();
  const categories = useCategories();
  const updateTx = useUpdateTransaction();
  const { data, isLoading, isError } = useTransactions({
    account_id: accountId || undefined,
    category: category || undefined,
    from: from || undefined,
    to: to || undefined,
    limit: LIMIT,
    offset,
  });

  const accountName = useMemo(() => {
    const map = new Map((accounts.data ?? []).map((a) => [a.id, a.name]));
    return (id: string) => map.get(id) ?? "—";
  }, [accounts.data]);

  const categoryNames = useMemo(
    () => (categories.data ?? []).map((c) => c.name),
    [categories.data],
  );

  function reset<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v);
      setOffset(0);
    };
  }

  const total = data?.total ?? 0;
  const page = Math.floor(offset / LIMIT) + 1;
  const pages = Math.max(1, Math.ceil(total / LIMIT));
  const net = (data?.total_income ?? 0) - (data?.total_expense ?? 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-mono text-2xl font-semibold text-foreground">Transações</h1>
        <Link href="/ledger/new">
          <Button>Nova transação</Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Conta" htmlFor="f-account">
          <Select
            id="f-account"
            value={accountId}
            onChange={(e) => reset(setAccountId)(e.target.value)}
          >
            <option value="">Todas</option>
            {(accounts.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Categoria" htmlFor="f-category">
          <Select
            id="f-category"
            value={category}
            onChange={(e) => reset(setCategory)(e.target.value)}
          >
            <option value="">Todas</option>
            {(categories.data ?? []).map((c) => (
              <option key={c.id} value={c.name}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="De" htmlFor="f-from">
          <Input id="f-from" type="date" value={from} onChange={(e) => reset(setFrom)(e.target.value)} />
        </Field>
        <Field label="Até" htmlFor="f-to">
          <Input id="f-to" type="date" value={to} onChange={(e) => reset(setTo)(e.target.value)} />
        </Field>
      </div>

      {/* totais discretos do conjunto filtrado */}
      {data && total > 0 && (
        <div className="flex flex-wrap justify-end gap-x-5 gap-y-1 text-xs text-foreground/50">
          <span>
            Receita <span className="tabular-nums text-gain">{formatBRL(data.total_income)}</span>
          </span>
          <span>
            Despesa <span className="tabular-nums text-loss">{formatBRL(data.total_expense)}</span>
          </span>
          <span>
            Líquido{" "}
            <span className={`tabular-nums ${net < 0 ? "text-loss" : "text-gain"}`}>
              {formatBRL(net)}
            </span>
          </span>
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-foreground/60">
            <tr>
              <th className="px-4 py-2.5 font-medium">Data</th>
              <th className="px-4 py-2.5 font-medium">Descrição</th>
              <th className="px-4 py-2.5 font-medium">Categoria</th>
              <th className="px-4 py-2.5 font-medium">Conta</th>
              <th className="px-4 py-2.5 text-right font-medium">Valor</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">
                  Carregando…
                </td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-loss">
                  Erro ao carregar transações.
                </td>
              </tr>
            )}
            {!isLoading && !isError && total === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground/50">
                  Nenhuma transação encontrada.
                </td>
              </tr>
            )}
            {(data?.items ?? []).map((tx) => (
              <TransactionRow
                key={tx.id}
                tx={tx}
                accountName={accountName}
                categoryNames={categoryNames}
                onSave={(id, patch) => updateTx.mutate({ id, patch })}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-foreground/60">
        <span>
          {total} transação(ões) · página {page} de {pages}
        </span>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - LIMIT))}
          >
            Anterior
          </Button>
          <Button
            variant="ghost"
            disabled={offset + LIMIT >= total}
            onClick={() => setOffset(offset + LIMIT)}
          >
            Próxima
          </Button>
        </div>
      </div>
    </div>
  );
}
