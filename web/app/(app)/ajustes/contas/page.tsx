"use client";

// Ajustes › Contas (Story 10.1 — FR-35, UX-DR43): conta, tipo (PF/MEI) e fonte, com criar e editar
// pelo Formulário em painel lateral. A conta MEI fica marcada como sem conferência de saldo (a
// conferência encadeada é só da PF; a MEI é sempre zerada).
import { useRef, useState } from "react";
import { toast } from "sonner";

import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { StatusBadge } from "@/components/data/StatusBadge";
import { FormField, SideForm } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAccounts, useSaveAccount } from "@/lib/ledger";
import type { Account } from "@/types/ledger";

const HOLDER = { pf: "PF", mei: "MEI" } as const;

function AccountForm({ account, onClose }: { account: Account | null; onClose: () => void }) {
  const save = useSaveAccount();
  const [name, setName] = useState(account?.name ?? "");
  const [holder, setHolder] = useState<"pf" | "mei">(account?.holder ?? "pf");
  const [number, setNumber] = useState(account?.account_number ?? "");
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const errors = { name: name.trim() ? null : "Informe o nome da conta." };
  const dirty =
    name !== (account?.name ?? "") ||
    holder !== (account?.holder ?? "pf") ||
    number !== (account?.account_number ?? "");

  function submit() {
    setTouched(true);
    if (errors.name) return;
    setFailed(false);
    save.mutate(
      {
        id: account?.id ?? null,
        body: {
          name: name.trim(),
          type: account?.type ?? "bank",
          holder,
          ...(number.trim() ? { account_number: number.trim() } : {}),
        },
      },
      {
        onSuccess: () => {
          toast(account ? "Conta salva." : "Conta cadastrada.");
          onClose();
        },
        onError: () => setFailed(true),
      },
    );
  }

  return (
    <SideForm
      open
      title={account ? "Editar conta" : "Nova conta"}
      description="A fonte do import segue o tipo: PF confere o saldo pelo OFX; MEI fica sem conferência."
      dirty={dirty}
      saving={save.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      <FormField id="conta-nome" label="Conta" error={touched ? errors.name : null}>
        <Input id="conta-nome" value={name} onChange={(e) => setName(e.target.value)} placeholder="Nubank PF" />
      </FormField>
      <FormField id="conta-tipo" label="Tipo">
        <select
          id="conta-tipo"
          value={holder}
          onChange={(e) => setHolder(e.target.value as "pf" | "mei")}
          className="h-9 w-40 rounded-md border border-input bg-background px-2 type-body-sm"
        >
          <option value="pf">PF</option>
          <option value="mei">MEI</option>
        </select>
      </FormField>
      <FormField id="conta-numero" label="Número da conta no extrato (opcional)">
        <Input id="conta-numero" value={number} onChange={(e) => setNumber(e.target.value)} className="type-num-body" />
      </FormField>
    </SideForm>
  );
}

export default function ContasPage() {
  const accounts = useAccounts();
  const [editing, setEditingState] = useState<Account | "nova" | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const setEditing = (next: Account | "nova" | null) => {
    if (next) opener.current = document.activeElement as HTMLElement | null;
    setEditingState(next);
    if (!next) requestAnimationFrame(() => opener.current?.focus());
  };

  const columns: DataColumn<Account>[] = [
    { id: "conta", header: "Conta", value: (a) => a.name },
    { id: "tipo", header: "Tipo", value: (a) => (a.holder ? HOLDER[a.holder] : "—") },
    { id: "fonte", header: "Fonte", value: (a) => a.fonte ?? "—" },
    {
      id: "saldo",
      header: "Saldo",
      value: (a) => (a.conferencia ? "conferido pelo OFX" : "sem conferência"),
      cell: (a) =>
        a.conferencia ? (
          <span className="type-body-sm">conferido pelo OFX</span>
        ) : (
          <StatusBadge tooltip="A conta MEI é sempre zerada: a conferência encadeada é só da PF.">sem conferência</StatusBadge>
        ),
    },
    {
      id: "acoes",
      header: "Ações",
      value: () => null,
      sortable: false,
      cell: (a) => (
        <button type="button" className="text-positive underline" onClick={() => setEditing(a)}>
          Editar
        </button>
      ),
    },
  ];

  if (accounts.isError && !accounts.data) {
    return <p className="type-body text-negative">Não foi possível carregar as contas.</p>;
  }
  const data = accounts.data ?? [];
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setEditing("nova")}>Nova conta</Button>
      </div>
      {!accounts.isLoading && data.length === 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card p-card-padding">
          <p className="type-body text-muted-foreground">Nenhuma conta. Cadastre a conta Nubank PF.</p>
          <Button variant="secondary" onClick={() => setEditing("nova")}>
            Nova conta
          </Button>
        </div>
      ) : (
        <DataTable
          tableId="ajustes-contas"
          caption="Contas"
          data={data}
          columns={columns}
          getRowId={(a) => a.id}
          empty={accounts.isLoading ? "Carregando…" : "Nenhuma conta. Cadastre a conta Nubank PF."}
        />
      )}
      {editing && (
        <AccountForm
          key={editing === "nova" ? "nova" : editing.id}
          account={editing === "nova" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
