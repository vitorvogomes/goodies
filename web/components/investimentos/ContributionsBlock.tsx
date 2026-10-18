"use client";

// Integralizações da debênture (P17): a lista que valora a debênture pela taxa, com o saldo de hoje
// de cada uma; incluir, corrigir data/valor e excluir (a ligada a uma transação sai recategorizando
// a transação). O saldo vem da API (AD-4).
import { useRef, useState } from "react";
import { toast } from "sonner";

import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { FormField, SideForm } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { formatBRL, formatDate, normalizeMoneyInput } from "@/lib/format";
import { currentDayBRT } from "@/lib/period";
import { useContributions, useDeleteContribution, useSaveContribution } from "@/lib/positions";
import type { Debenture, DebentureContribution } from "@/types/positions";

const FAILED = "Não foi possível salvar. Nada foi perdido.";

function ContributionForm({
  debenture,
  item,
  onClose,
}: {
  debenture: Debenture;
  item: DebentureContribution | null;
  onClose: () => void;
}) {
  const save = useSaveContribution(debenture.id);
  const shownValue = item ? item.valor.toFixed(2).replace(".", ",") : "";
  const [day, setDay] = useState(item?.data ?? currentDayBRT());
  const [value, setValue] = useState(shownValue);
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const normalized = normalizeMoneyInput(value);
  const errors = {
    day: !/^\d{4}-\d{2}-\d{2}$/.test(day)
      ? "Informe a data."
      : day > currentDayBRT()
        ? "A data não pode ser depois de hoje."
        : null,
    value: normalized && !normalized.startsWith("-") && Number(normalized) > 0 ? null : "Informe o valor (ex.: 1.000,00).",
  };
  const dirty = day !== (item?.data ?? currentDayBRT()) || value !== shownValue;

  function submit() {
    setTouched(true);
    if (Object.values(errors).some(Boolean) || !normalized) return;
    setFailed(false);
    save.mutate(
      { id: item?.id ?? null, data: day, valor: normalized },
      {
        onSuccess: () => {
          toast(item ? "Integralização salva." : "Integralização incluída.");
          onClose();
        },
        onError: (err) => {
          if (err instanceof ApiError && err.status === 422) toast(apiErrorMessage(err.detail, FAILED));
          setFailed(true);
        },
      },
    );
  }

  return (
    <SideForm
      open
      title={item ? "Editar integralização" : "Nova integralização"}
      description={`${debenture.issuer} · ${debenture.rate_label}. O saldo de hoje é calculado pela taxa cadastrada.`}
      dirty={dirty}
      saving={save.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      <FormField id="integ-data" label="Data" error={touched ? errors.day : null}>
        <Input id="integ-data" type="date" max={currentDayBRT()} value={day} onChange={(e) => setDay(e.target.value)} className="w-44" />
      </FormField>
      <FormField id="integ-valor" label="Valor integralizado (R$)" error={touched ? errors.value : null}>
        <Input id="integ-valor" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} className="w-44 type-num-body" />
      </FormField>
    </SideForm>
  );
}

export function ContributionsBlock({ debenture }: { debenture: Debenture }) {
  const contributions = useContributions(debenture.id);
  const remove = useDeleteContribution(debenture.id);
  const [editing, setEditingState] = useState<DebentureContribution | "nova" | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const setEditing = (next: DebentureContribution | "nova" | null) => {
    if (next) opener.current = document.activeElement as HTMLElement | null;
    setEditingState(next);
    if (!next) requestAnimationFrame(() => opener.current?.focus());
  };
  const data = contributions.data ?? [];
  const total = data.length;

  const columns: DataColumn<DebentureContribution>[] = [
    { id: "data", header: "Data", value: (c) => c.data, cell: (c) => formatDate(c.data), className: "type-num-table" },
    { id: "valor", header: "Valor", value: (c) => c.valor, numeric: true, cell: (c) => formatBRL(c.valor) },
    { id: "saldo", header: "Saldo hoje", value: (c) => c.saldo, numeric: true, cell: (c) => formatBRL(c.saldo) },
    {
      id: "transacao",
      header: "Saída da conta",
      value: (c) => c.transacao,
      cell: (c) => <span className="block max-w-72 truncate text-muted-foreground">{c.transacao ?? "lançada à mão"}</span>,
      detailOnly: true,
    },
    {
      id: "acoes",
      header: "Ações",
      value: () => null,
      sortable: false,
      cell: (c) => (
        <span className="inline-flex gap-3">
          <button type="button" className="text-positive underline" onClick={() => setEditing(c)}>
            Editar
          </button>
          {c.transacao === null && (
            <button
              type="button"
              className="text-negative underline"
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(c.id, {
                  onSuccess: () => toast("Integralização excluída."),
                  onError: () => toast("Não foi possível excluir. Nada foi perdido."),
                })
              }
            >
              Excluir
            </button>
          )}
        </span>
      ),
    },
  ];

  return (
    <section aria-labelledby={`integ-${debenture.id}`} className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={`integ-${debenture.id}`} className="type-section-title">
          Integralizações · {debenture.issuer}
          <span className="ml-2 type-caption text-muted-foreground">{total} lançamento(s)</span>
        </h2>
        <Button variant="secondary" onClick={() => setEditing("nova")}>
          Nova integralização
        </Button>
      </div>
      {contributions.isError && !contributions.data ? (
        <p className="type-body text-negative">Não foi possível carregar as integralizações.</p>
      ) : (
        <DataTable
          tableId={`debenture-integralizacoes`}
          caption={`Integralizações da debênture ${debenture.issuer}`}
          data={data}
          columns={columns}
          getRowId={(c) => c.id}
          empty={contributions.isLoading ? "Carregando…" : "Nenhuma integralização."}
        />
      )}
      {editing && (
        <ContributionForm
          key={editing === "nova" ? "nova" : editing.id}
          debenture={debenture}
          item={editing === "nova" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  );
}
