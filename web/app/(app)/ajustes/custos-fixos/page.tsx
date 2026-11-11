"use client";

// Ajustes › Custos e receitas (Story 6.1 — FR-18, UX-DR43; receitas esperadas a pedido de
// 18/10/2026): o cadastro. Criar e editar (nome, valor, vencimento, categoria) no Formulário em
// painel lateral; o valor, campo único, edita inline (Enter grava, Esc reverte). O estado do mês
// (pago × pendente) fica em Caixa › Custos fixos; o planejado × recebido, em Caixa › Orçamento.
import { useRef, useState } from "react";
import { toast } from "sonner";

import { CategoryCombobox } from "@/components/caixa/CategoryCombobox";
import { ExpectedIncomes } from "@/components/caixa/ExpectedIncomes";
import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { RowActions } from "@/components/data/RowActions";
import { FormField, SAVE_FAILED, SideForm } from "@/components/forms/SideForm";
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
import { formatBRL, normalizeMoneyInput } from "@/lib/format";
import {
  useCategoryOptions,
  useDeleteFixedCostItem,
  useFixedCostItems,
  useSaveFixedCostItem,
} from "@/lib/ledger";
import type { CategoryOption, FixedCostItem as FixedCost } from "@/types/ledger";

const DUE_ERROR = "Vencimento entre 1 e 31.";
const AMOUNT_ERROR = "Informe um valor maior que zero (ex.: 450,00).";

function toInput(value: number): string {
  return value.toFixed(2).replace(".", ",");
}

function dueError(raw: string): string | null {
  const n = Number(raw);
  return /^\d{1,2}$/.test(raw) && n >= 1 && n <= 31 ? null : DUE_ERROR;
}

function FixedCostForm({
  cost,
  options,
  onClose,
}: {
  cost: FixedCost | null;
  options: CategoryOption[];
  onClose: () => void;
}) {
  const save = useSaveFixedCostItem();
  const [name, setName] = useState(cost?.name ?? "");
  const [amount, setAmount] = useState(cost ? toInput(cost.amount) : "");
  const [due, setDue] = useState(cost ? String(cost.due_day) : "");
  const [category, setCategory] = useState<CategoryOption | null>(
    cost ? (options.find((o) => o.id === cost.category_id) ?? null) : null,
  );
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const money = normalizeMoneyInput(amount);
  const errors = {
    name: name.trim() ? null : "Informe o nome.",
    amount: money && Number(money) > 0 ? null : AMOUNT_ERROR,
    due: dueError(due.trim()),
    category: category ? null : "Escolha a categoria.",
  };
  const dirty =
    name !== (cost?.name ?? "") ||
    amount !== (cost ? toInput(cost.amount) : "") ||
    due !== (cost ? String(cost.due_day) : "") ||
    category?.id !== cost?.category_id;

  function submit() {
    setTouched(true);
    if (Object.values(errors).some(Boolean) || !money || !category) return;
    setFailed(false);
    save.mutate(
      {
        id: cost?.id ?? null,
        body: { name: name.trim(), amount: money, due_day: Number(due), category_id: category.id },
      },
      {
        onSuccess: () => {
          toast(cost ? "Custo fixo salvo." : "Custo fixo cadastrado.");
          onClose();
        },
        onError: () => setFailed(true),
      },
    );
  }

  const shown = (key: keyof typeof errors) => (touched ? errors[key] : null);
  return (
    <SideForm
      open
      title={cost ? "Editar custo fixo" : "Novo custo fixo"}
      description="Casa sozinho com a transação do mês (±10% do valor, até 5 dias do vencimento)."
      dirty={dirty}
      saving={save.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      <FormField id="cf-nome" label="Nome" error={shown("name")}>
        <Input id="cf-nome" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={Boolean(shown("name"))} />
      </FormField>
      <FormField id="cf-valor" label="Valor (R$)" error={shown("amount")}>
        <Input
          id="cf-valor"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          aria-invalid={Boolean(shown("amount"))}
          className="type-num-body text-right"
          placeholder="0,00"
        />
      </FormField>
      <FormField id="cf-vencimento" label="Vencimento (dia do mês)" error={shown("due")}>
        <Input
          id="cf-vencimento"
          inputMode="numeric"
          value={due}
          onChange={(e) => setDue(e.target.value)}
          aria-invalid={Boolean(shown("due"))}
          className="type-num-body w-24"
        />
      </FormField>
      <FormField id="cf-categoria" label="Categoria" error={shown("category")}>
        <CategoryCombobox
          options={options}
          value={category?.id ?? null}
          label={category?.label ?? "Escolha a categoria"}
          empty={!category}
          onSelect={setCategory}
        />
      </FormField>
    </SideForm>
  );
}

/** Valor editável inline: Enter grava, Esc reverte; falha mantém o digitado e oferece tentar de novo. */
function InlineAmount({ cost }: { cost: FixedCost }) {
  const save = useSaveFixedCostItem();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(toInput(cost.amount));
  const [error, setError] = useState<string | null>(null);

  function commit() {
    const money = normalizeMoneyInput(value);
    if (!money || Number(money) <= 0) {
      setError(AMOUNT_ERROR);
      return;
    }
    setError(null);
    save.mutate(
      { id: cost.id, body: { amount: money } },
      {
        onSuccess: () => {
          setEditing(false);
          toast("Valor salvo.");
        },
        onError: () => setError(`${SAVE_FAILED} Tentar de novo.`),
      },
    );
  }

  if (!editing) {
    return (
      <button
        type="button"
        className="type-num-table underline decoration-dotted underline-offset-4"
        aria-label={`Editar valor de ${cost.name}`}
        onClick={() => {
          setValue(toInput(cost.amount));
          setEditing(true);
        }}
      >
        {formatBRL(cost.amount)}
      </button>
    );
  }
  return (
    <span className="inline-flex flex-col items-end gap-1">
      <Input
        autoFocus
        aria-label={`Valor de ${cost.name}`}
        inputMode="decimal"
        value={value}
        disabled={save.isPending}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") {
            setEditing(false);
            setError(null);
          }
        }}
        className="h-8 w-32 type-num-body text-right"
        aria-invalid={Boolean(error)}
      />
      {error && (
        <span role="alert" className="type-caption text-negative">
          {error}
        </span>
      )}
    </span>
  );
}

export default function CustosFixosPage() {
  const costs = useFixedCostItems();
  const options = useCategoryOptions();
  const remove = useDeleteFixedCostItem();
  const [editing, setEditingState] = useState<FixedCost | "novo" | null>(null);
  const [deleting, setDeleting] = useState<FixedCost | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const setEditing = (next: FixedCost | "novo" | null) => {
    if (next) opener.current = document.activeElement as HTMLElement | null;
    setEditingState(next);
    if (!next) requestAnimationFrame(() => opener.current?.focus());
  };

  const columns: DataColumn<FixedCost>[] = [
    { id: "nome", header: "Custo", value: (c) => c.name },
    { id: "valor", header: "Valor", value: (c) => c.amount, numeric: true, cell: (c) => <InlineAmount cost={c} />, mobile: "aside" },
    { id: "vencimento", header: "Vencimento", value: (c) => c.due_day, cell: (c) => `dia ${c.due_day}`, mobile: "meta" },
    { id: "categoria", header: "Categoria", value: (c) => c.category_label, mobile: "meta" },
    {
      id: "acoes",
      header: "Ações",
      value: () => null,
      sortable: false,
      actions: true,
      cell: (c) => <RowActions subject={c.name} onEdit={() => setEditing(c)} onDelete={() => setDeleting(c)} />,
    },
  ];

  if (costs.isError) return <p className="type-body text-negative">Não foi possível carregar os custos fixos.</p>;

  return (
    <div className="space-y-8">
      <section aria-labelledby="custos-fixos-cadastro" className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 id="custos-fixos-cadastro" className="type-section-title">
            Custos fixos
          </h2>
          <Button onClick={() => setEditing("novo")}>Novo custo fixo</Button>
        </div>
        <DataTable
          tableId="ajustes-custos-fixos"
          caption="Custos fixos"
          data={costs.data ?? []}
          columns={columns}
          getRowId={(c) => c.id}
          empty={costs.isLoading ? "Carregando…" : "Nenhum custo fixo. Cadastre para acompanhar pago × pendente."}
        />
        {editing && (
          <FixedCostForm
            key={editing === "novo" ? "novo" : editing.id}
            cost={editing === "novo" ? null : editing}
            options={options.data ?? []}
            onClose={() => setEditing(null)}
          />
        )}
        <AlertDialog open={deleting !== null} onOpenChange={(v) => (v ? undefined : setDeleting(null))}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Excluir {deleting?.name}?</AlertDialogTitle>
              <AlertDialogDescription>
                Os meses em que ele já foi pago continuam com ele; a partir deste mês, sai da lista.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel autoFocus>Cancelar</AlertDialogCancel>
              <AlertDialogAction
                onClick={() =>
                  deleting &&
                  remove.mutate(deleting.id, {
                    onSuccess: () => toast("Custo fixo excluído."),
                    onError: () => toast(SAVE_FAILED),
                  })
                }
              >
                Excluir
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </section>
      <ExpectedIncomes />
    </div>
  );
}
