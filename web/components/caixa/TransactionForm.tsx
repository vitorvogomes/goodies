"use client";

// "Nova transação" / "Editar transação" (Story 2.8): conta, data, valor, descrição e categoria num
// Formulário em painel lateral. O sinal do valor vem do tipo da categoria (receita +, gasto e
// investimento −; transferência pergunta entrada ou saída). Validação ao sair do campo e no Salvar.
import { useState } from "react";
import { toast } from "sonner";

import { CategoryCombobox } from "@/components/caixa/CategoryCombobox";
import { FormField, SideForm } from "@/components/forms/SideForm";
import { Input } from "@/components/ui/input";
import { normalizeMoneyInput } from "@/lib/format";
import { type ManualTransactionIn, useAccounts, useSaveManualTransaction } from "@/lib/ledger";
import type { CategoryOption, LedgerTransaction } from "@/types/ledger";

type Field = "account" | "date" | "amount" | "category";

function initialAmount(tx: LedgerTransaction | null): string {
  if (!tx) return "";
  return Math.abs(tx.amount).toFixed(2).replace(".", ",");
}

export function TransactionForm({
  open,
  transaction,
  options,
  onClose,
}: {
  open: boolean;
  transaction: LedgerTransaction | null;
  options: CategoryOption[];
  onClose: () => void;
}) {
  const accounts = useAccounts();
  const save = useSaveManualTransaction();
  const editing = transaction !== null;
  const [accountId, setAccountId] = useState(transaction?.account_id ?? "");
  const [date, setDate] = useState(transaction?.date ?? "");
  const [amount, setAmount] = useState(initialAmount(transaction));
  const [incoming, setIncoming] = useState((transaction?.amount ?? -1) > 0);
  const [description, setDescription] = useState(transaction?.description ?? "");
  const [category, setCategory] = useState<CategoryOption | null>(
    options.find((o) => o.id === transaction?.category_id) ?? null,
  );
  const [touched, setTouched] = useState<Set<Field>>(new Set());
  const [failed, setFailed] = useState(false);

  const magnitude = normalizeMoneyInput(amount.replace(/^[+-]/, ""));
  const errors: Record<Field, string | null> = {
    account: accountId ? null : "Escolha a conta.",
    date: /^\d{4}-\d{2}-\d{2}$/.test(date) ? null : "Informe a data.",
    amount:
      magnitude && Number(magnitude) > 0 ? null : "Informe um valor maior que zero (ex.: 42,90).",
    category: category ? null : "Escolha a categoria.",
  };
  const shown = (f: Field) => (touched.has(f) ? errors[f] : null);
  const touch = (f: Field) => setTouched((t) => new Set(t).add(f));
  const dirty =
    accountId !== (transaction?.account_id ?? "") ||
    date !== (transaction?.date ?? "") ||
    amount !== initialAmount(transaction) ||
    description !== (transaction?.description ?? "") ||
    (category?.id ?? null) !== (transaction?.category_id ?? null);

  // Editando sem trocar a categoria, o sinal original fica (um estorno em gasto continua +).
  const sign = (opt: CategoryOption) => {
    if (transaction && opt.id === transaction.category_id && opt.kind !== "transfer") {
      return transaction.amount > 0 ? "" : "-";
    }
    return opt.kind === "income" || (opt.kind === "transfer" && incoming) ? "" : "-";
  };

  function submit() {
    setTouched(new Set<Field>(["account", "date", "amount", "category"]));
    if (Object.values(errors).some(Boolean) || !category || !magnitude) return;
    const body: ManualTransactionIn = {
      account_id: accountId,
      date,
      amount: `${sign(category)}${magnitude}`,
      description: description.trim() || null,
      category_id: category.id,
    };
    setFailed(false);
    save.mutate(
      { id: transaction?.id, body },
      {
        onSuccess: () => {
          toast(editing ? "Transação salva." : "Transação lançada.");
          onClose();
        },
        onError: () => setFailed(true),
      },
    );
  }

  return (
    <SideForm
      open={open}
      title={editing ? "Editar transação" : "Nova transação"}
      description="Lançamento à mão: gasto em dinheiro ou ajuste."
      dirty={dirty}
      saving={save.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      <FormField id="tx-conta" label="Conta" error={shown("account")}>
        <select
          id="tx-conta"
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          onBlur={() => touch("account")}
          aria-invalid={Boolean(shown("account"))}
          className="h-9 w-full rounded-md border border-input bg-background px-3 type-body"
        >
          <option value="">Escolha…</option>
          {(accounts.data ?? []).map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </FormField>
      <FormField id="tx-data" label="Data" error={shown("date")}>
        <Input
          id="tx-data"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          onBlur={() => touch("date")}
          aria-invalid={Boolean(shown("date"))}
        />
      </FormField>
      <FormField id="tx-valor" label="Valor (R$)" error={shown("amount")}>
        <Input
          id="tx-valor"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          onBlur={() => touch("amount")}
          aria-invalid={Boolean(shown("amount"))}
          className="type-num-body text-right"
          placeholder="0,00"
        />
      </FormField>
      <FormField id="tx-descricao" label="Descrição">
        <Input
          id="tx-descricao"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </FormField>
      <FormField id="tx-categoria" label="Categoria" error={shown("category")}>
        <div onBlur={() => touch("category")}>
          <CategoryCombobox
            options={options}
            value={category?.id ?? null}
            label={category?.label ?? "Escolha a categoria"}
            empty={!category}
            onSelect={(o) => {
              setCategory(o);
              touch("category");
            }}
          />
        </div>
      </FormField>
      {category?.kind === "transfer" && (
        <fieldset className="space-y-1.5">
          <legend className="type-body-sm font-semibold">Direção</legend>
          <div className="flex gap-4 type-body">
            <label className="flex items-center gap-2">
              <input type="radio" checked={!incoming} onChange={() => setIncoming(false)} /> Saída
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={incoming} onChange={() => setIncoming(true)} /> Entrada
            </label>
          </div>
        </fieldset>
      )}
    </SideForm>
  );
}
