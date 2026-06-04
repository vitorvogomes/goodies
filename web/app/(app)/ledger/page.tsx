"use client";

// STORY-01-10 — lista de transações com filtros (conta, categoria, intervalo) + paginação.
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button, Field, Input, Select } from "@/components/ui";
import { formatBRL, formatDate } from "@/lib/format";
import { useAccounts, useCategories, useTransactions } from "@/lib/ledger";

const LIMIT = 50;

export default function LedgerPage() {
  const [accountId, setAccountId] = useState("");
  const [category, setCategory] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [offset, setOffset] = useState(0);

  const accounts = useAccounts();
  const categories = useCategories();
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

  // qualquer mudança de filtro volta p/ a primeira página
  function reset<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v);
      setOffset(0);
    };
  }

  const total = data?.total ?? 0;
  const page = Math.floor(offset / LIMIT) + 1;
  const pages = Math.max(1, Math.ceil(total / LIMIT));

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
              <tr key={tx.id} className="border-t border-border">
                <td className="px-4 py-2.5 tabular-nums text-foreground/80">{formatDate(tx.date)}</td>
                <td className="px-4 py-2.5 text-foreground/80">{tx.description ?? "—"}</td>
                <td className="px-4 py-2.5 text-foreground/60">{tx.category}</td>
                <td className="px-4 py-2.5 text-foreground/60">{accountName(tx.account_id)}</td>
                <td
                  className={`px-4 py-2.5 text-right tabular-nums ${
                    tx.amount < 0 ? "text-loss" : "text-gain"
                  }`}
                >
                  {formatBRL(tx.amount)}
                </td>
              </tr>
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
