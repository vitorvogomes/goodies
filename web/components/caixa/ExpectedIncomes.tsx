"use client";

// Receitas esperadas (Ajustes › Custos e receitas): o planejamento das receitas
// do mês — salário, pagamentos a receber. O recebido sai das entradas do trabalho do pagador no mês
// (Caixa › Orçamento mostra planejado × recebido e o disponível com o que falta receber).
import { useRef, useState } from "react";
import { toast } from "sonner";

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
import { formatBRL, formatMonth, normalizeMoneyInput } from "@/lib/format";
import {
  type ExpectedIncome,
  useDeleteExpectedIncome,
  useExpectedIncomes,
  useSaveExpectedIncome,
} from "@/lib/ledger";
import { currentDayBRT } from "@/lib/period";

const AMOUNT_ERROR = "Informe um valor maior que zero (ex.: 1.200,00).";

function toInput(value: number): string {
  return value.toFixed(2).replace(".", ",");
}

function IncomeForm({ income, onClose }: { income: ExpectedIncome | null; onClose: () => void }) {
  const save = useSaveExpectedIncome();
  const [name, setName] = useState(income?.name ?? "");
  const [amount, setAmount] = useState(income ? toInput(income.amount) : "");
  const [due, setDue] = useState(income ? String(income.due_day) : "");
  const [payer, setPayer] = useState(income?.payer ?? "");
  const [month, setMonth] = useState(currentDayBRT().slice(0, 7));
  const [onlyMonth, setOnlyMonth] = useState(false);
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const money = normalizeMoneyInput(amount);
  const day = Number(due.trim());
  const errors = {
    name: name.trim() ? null : "Informe o nome.",
    amount: money && Number(money) > 0 ? null : AMOUNT_ERROR,
    due: /^\d{1,2}$/.test(due.trim()) && day >= 1 && day <= 31 ? null : "Dia entre 1 e 31.",
    month: income || /^\d{4}-\d{2}$/.test(month) ? null : "Informe o mês.",
  };
  const dirty =
    name !== (income?.name ?? "") ||
    amount !== (income ? toInput(income.amount) : "") ||
    due !== (income ? String(income.due_day) : "") ||
    payer !== (income?.payer ?? "");

  function submit() {
    setTouched(true);
    if (Object.values(errors).some(Boolean) || !money) return;
    setFailed(false);
    const body = income
      ? { name: name.trim(), amount: money, due_day: day, payer: payer.trim() }
      : {
          name: name.trim(),
          amount: money,
          due_day: day,
          payer: payer.trim(),
          valid_from: `${month}-01`,
          only_month: onlyMonth,
        };
    save.mutate(
      { id: income?.id ?? null, body },
      {
        onSuccess: () => {
          toast(income ? "Receita salva." : "Receita cadastrada.");
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
      title={income ? "Editar receita esperada" : "Nova receita esperada"}
      description="O recebido vem das entradas do trabalho com este pagador no mês (sem pagador, pela palavra do nome na descrição)."
      dirty={dirty || (!income && (onlyMonth || month !== currentDayBRT().slice(0, 7)))}
      saving={save.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      <FormField id="re-nome" label="Nome" error={shown("name")}>
        <Input id="re-nome" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={Boolean(shown("name"))} />
      </FormField>
      <FormField id="re-valor" label="Valor esperado (R$)" error={shown("amount")}>
        <Input
          id="re-valor"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          aria-invalid={Boolean(shown("amount"))}
          className="type-num-body text-right"
          placeholder="0,00"
        />
      </FormField>
      <FormField id="re-dia" label="Dia previsto" error={shown("due")}>
        <Input
          id="re-dia"
          inputMode="numeric"
          value={due}
          onChange={(e) => setDue(e.target.value)}
          aria-invalid={Boolean(shown("due"))}
          className="type-num-body w-24"
        />
      </FormField>
      <FormField id="re-pagador" label="Pagador (como aparece em Caixa › Transações)">
        <Input id="re-pagador" value={payer} onChange={(e) => setPayer(e.target.value)} placeholder="Flash" />
      </FormField>
      {!income && (
        <>
          <FormField id="re-mes" label="A partir de" error={shown("month")}>
            <Input id="re-mes" type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-44" />
          </FormField>
          <label className="flex items-center gap-2 type-body-sm">
            <input type="checkbox" checked={onlyMonth} onChange={(e) => setOnlyMonth(e.target.checked)} />
            Só neste mês (pagamento a receber, não se repete)
          </label>
        </>
      )}
    </SideForm>
  );
}

export function ExpectedIncomes() {
  const incomes = useExpectedIncomes();
  const remove = useDeleteExpectedIncome();
  const [editing, setEditingState] = useState<ExpectedIncome | "nova" | null>(null);
  const [deleting, setDeleting] = useState<ExpectedIncome | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const setEditing = (next: ExpectedIncome | "nova" | null) => {
    if (next) opener.current = document.activeElement as HTMLElement | null;
    setEditingState(next);
    if (!next) requestAnimationFrame(() => opener.current?.focus());
  };

  const columns: DataColumn<ExpectedIncome>[] = [
    { id: "nome", header: "Receita", value: (i) => i.name },
    { id: "valor", header: "Valor", value: (i) => i.amount, numeric: true, cell: (i) => formatBRL(i.amount), mobile: "aside" },
    { id: "dia", header: "Dia", value: (i) => i.due_day, cell: (i) => `dia ${i.due_day}`, mobile: "meta" },
    { id: "pagador", header: "Pagador", value: (i) => i.payer ?? "—", mobile: "meta" },
    {
      id: "vigencia",
      header: "Quando",
      value: (i) => i.valid_from,
      cell: (i) =>
        i.valid_to === i.valid_from ? `só ${formatMonth(i.valid_from.slice(0, 7))}` : `todo mês desde ${formatMonth(i.valid_from.slice(0, 7))}`,
    },
    {
      id: "acoes",
      header: "Ações",
      value: () => null,
      sortable: false,
      actions: true,
      cell: (i) => <RowActions subject={i.name} onEdit={() => setEditing(i)} onDelete={() => setDeleting(i)} />,
    },
  ];

  if (incomes.isError) return <p className="type-body text-negative">Não foi possível carregar as receitas esperadas.</p>;
  return (
    <section aria-labelledby="receitas-esperadas" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="receitas-esperadas" className="type-section-title">
          Receitas esperadas
        </h2>
        <Button onClick={() => setEditing("nova")}>Nova receita</Button>
      </div>
      <DataTable
        tableId="ajustes-receitas"
        caption="Receitas esperadas"
        data={incomes.data ?? []}
        columns={columns}
        getRowId={(i) => i.id}
        empty={incomes.isLoading ? "Carregando…" : "Nenhuma receita esperada. Cadastre para ver planejado × recebido no orçamento."}
      />
      {editing && (
        <IncomeForm
          key={editing === "nova" ? "nova" : editing.id}
          income={editing === "nova" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
      <AlertDialog open={deleting !== null} onOpenChange={(v) => (v ? undefined : setDeleting(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir {deleting?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Os meses passados continuam com ela; a partir deste mês, sai do orçamento.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel autoFocus>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleting &&
                remove.mutate(deleting.id, {
                  onSuccess: () => toast("Receita excluída."),
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
  );
}
