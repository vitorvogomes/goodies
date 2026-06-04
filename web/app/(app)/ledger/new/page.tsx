"use client";

// STORY-01-11 — formulário de nova transação. O usuário escolhe tipo (receita/
// despesa) + valor positivo; o sinal é aplicado no envio (backend: + receita, − despesa).
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { ApiError } from "@/lib/api";
import { Button, Field, Input, Select } from "@/components/ui";
import { useAccounts, useCategories, useCreateTransaction } from "@/lib/ledger";
import type { CategoryKind } from "@/types/ledger";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function NewTransactionPage() {
  const router = useRouter();
  const accounts = useAccounts();
  const createTransaction = useCreateTransaction();

  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [accountId, setAccountId] = useState("");
  const [date, setDate] = useState(today());
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [isRecurring, setIsRecurring] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const categories = useCategories(kind as CategoryKind);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const value = Number.parseFloat(amount.replace(",", "."));
    if (!accountId || !category || !date || !(value > 0)) {
      setError("Preencha conta, categoria, data e um valor maior que zero.");
      return;
    }
    createTransaction.mutate(
      {
        account_id: accountId,
        date,
        amount: kind === "expense" ? -value : value,
        category,
        description: description || undefined,
        is_recurring: isRecurring,
      },
      {
        onSuccess: () => router.push("/ledger"),
        onError: (err) =>
          setError(
            err instanceof ApiError && err.status === 422
              ? "Dados inválidos. Verifique a conta e o valor."
              : "Não foi possível salvar. Tente novamente.",
          ),
      },
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h1 className="font-mono text-2xl font-semibold text-foreground">Nova transação</h1>

      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <Field label="Tipo" htmlFor="t-kind">
          <Select
            id="t-kind"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value as "expense" | "income");
              setCategory("");
            }}
          >
            <option value="expense">Despesa</option>
            <option value="income">Receita</option>
          </Select>
        </Field>

        <Field label="Conta" htmlFor="t-account">
          <Select id="t-account" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
            <option value="">Selecione…</option>
            {(accounts.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Data" htmlFor="t-date">
            <Input id="t-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
          <Field label="Valor (R$)" htmlFor="t-amount">
            <Input
              id="t-amount"
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              placeholder="0,00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </Field>
        </div>

        <Field label="Categoria" htmlFor="t-category">
          <Select id="t-category" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Selecione…</option>
            {(categories.data ?? []).map((c) => (
              <option key={c.id} value={c.name}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Descrição (opcional)" htmlFor="t-desc">
          <Input
            id="t-desc"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>

        <label className="flex items-center gap-2 text-sm text-foreground/80">
          <input
            type="checkbox"
            checked={isRecurring}
            onChange={(e) => setIsRecurring(e.target.checked)}
            className="h-4 w-4 rounded border-border bg-background accent-accent"
          />
          Recorrente (receita/despesa fixa mensal)
        </label>

        {error && (
          <p role="alert" className="text-sm text-loss">
            {error}
          </p>
        )}

        <div className="flex gap-2">
          <Button type="submit" disabled={createTransaction.isPending}>
            {createTransaction.isPending ? "Salvando…" : "Salvar"}
          </Button>
          <Button type="button" variant="ghost" onClick={() => router.push("/ledger")}>
            Cancelar
          </Button>
        </div>
      </form>
    </div>
  );
}
