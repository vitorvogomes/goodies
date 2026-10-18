"use client";

// Ajustes › Debêntures (Story 7.6 — FR-24, UX-DR43): o cadastro que substitui o JSON mantido à mão —
// emissor, taxa (rótulo e fator mensal), início e vencimento — no Formulário em painel lateral. A
// debênture é valorada pela taxa cadastrada; o aporte é sugerido na Revisão de transações.
import { useRef, useState } from "react";
import { toast } from "sonner";

import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { ContributionsBlock } from "@/components/investimentos/ContributionsBlock";
import { FormField, SideForm } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatBRL, formatDate } from "@/lib/format";
import { useDebentures, useSaveDebenture } from "@/lib/positions";
import type { Debenture } from "@/types/positions";

function toInput(v: number): string {
  return String(Number(v)).replace(".", ",");
}

function DebentureForm({ debenture, onClose }: { debenture: Debenture | null; onClose: () => void }) {
  const save = useSaveDebenture();
  const [issuer, setIssuer] = useState(debenture?.issuer ?? "");
  const [rate, setRate] = useState(debenture?.rate_label ?? "");
  const [factor, setFactor] = useState(debenture ? toInput(debenture.monthly_factor) : "");
  const [start, setStart] = useState(debenture?.start_date ?? "");
  const [maturity, setMaturity] = useState(debenture?.maturity_date ?? "");
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const factorValue = factor.trim().replace(",", ".");
  const errors = {
    issuer: issuer.trim() ? null : "Informe o emissor.",
    rate: rate.trim() ? null : "Informe a taxa (ex.: Pré 24% a.a.).",
    factor: /^\d+(\.\d{1,6})?$/.test(factorValue) && Number(factorValue) > 0 ? null : "Informe o fator mensal (ex.: 1,78).",
    start: /^\d{4}-\d{2}-\d{2}$/.test(start) ? null : "Informe o início.",
    maturity: !maturity || maturity >= start ? null : "O vencimento vem depois do início.",
  };
  const dirty =
    issuer !== (debenture?.issuer ?? "") ||
    rate !== (debenture?.rate_label ?? "") ||
    factor !== (debenture ? toInput(debenture.monthly_factor) : "") ||
    start !== (debenture?.start_date ?? "") ||
    maturity !== (debenture?.maturity_date ?? "");

  function submit() {
    setTouched(true);
    if (Object.values(errors).some(Boolean)) return;
    setFailed(false);
    save.mutate(
      {
        id: debenture?.id ?? null,
        body: {
          issuer: issuer.trim(),
          rate_label: rate.trim(),
          monthly_factor: factorValue,
          start_date: start,
          maturity_date: maturity || null,
        },
      },
      {
        onSuccess: () => {
          toast(debenture ? "Debênture salva." : "Debênture cadastrada.");
          onClose();
        },
        onError: () => setFailed(true),
      },
    );
  }

  const shown = (k: keyof typeof errors) => (touched ? errors[k] : null);
  return (
    <SideForm
      open
      title={debenture ? "Editar debênture" : "Nova debênture"}
      description="Valorada pela taxa cadastrada; o aporte aparece sugerido na Revisão de transações."
      dirty={dirty}
      saving={save.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      <FormField id="deb-emissor" label="Emissor" error={shown("issuer")}>
        <Input id="deb-emissor" value={issuer} onChange={(e) => setIssuer(e.target.value)} />
      </FormField>
      <FormField id="deb-taxa" label="Taxa" error={shown("rate")}>
        <Input id="deb-taxa" value={rate} placeholder="Pré 24% a.a." onChange={(e) => setRate(e.target.value)} />
      </FormField>
      <FormField id="deb-fator" label="Fator mensal (% a.m.)" error={shown("factor")}>
        <Input
          id="deb-fator"
          inputMode="decimal"
          value={factor}
          placeholder="1,78"
          onChange={(e) => setFactor(e.target.value)}
          className="type-num-body w-32"
        />
      </FormField>
      <FormField id="deb-inicio" label="Início" error={shown("start")}>
        <Input id="deb-inicio" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="w-44" />
      </FormField>
      <FormField id="deb-vencimento" label="Vencimento" error={shown("maturity")}>
        <Input
          id="deb-vencimento"
          type="date"
          value={maturity}
          onChange={(e) => setMaturity(e.target.value)}
          className="w-44"
        />
      </FormField>
    </SideForm>
  );
}

export default function DebenturesPage() {
  const debentures = useDebentures();
  const [editing, setEditingState] = useState<Debenture | "nova" | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const setEditing = (next: Debenture | "nova" | null) => {
    if (next) opener.current = document.activeElement as HTMLElement | null;
    setEditingState(next);
    if (!next) requestAnimationFrame(() => opener.current?.focus());
  };

  const columns: DataColumn<Debenture>[] = [
    { id: "emissor", header: "Emissor", value: (d) => d.issuer },
    { id: "taxa", header: "Taxa", value: (d) => d.rate_label, cell: (d) => `${d.rate_label} (${toInput(d.monthly_factor)}% a.m.)` },
    { id: "inicio", header: "Início", value: (d) => d.start_date, cell: (d) => formatDate(d.start_date) },
    {
      id: "vencimento",
      header: "Vencimento",
      value: (d) => d.maturity_date,
      cell: (d) => (d.maturity_date ? formatDate(d.maturity_date) : "—"),
    },
    { id: "aplicado", header: "Aplicado", value: (d) => d.aplicado, numeric: true, cell: (d) => formatBRL(d.aplicado) },
    {
      id: "acoes",
      header: "Ações",
      value: () => null,
      sortable: false,
      cell: (d) => (
        <button type="button" className="text-positive underline" onClick={() => setEditing(d)}>
          Editar
        </button>
      ),
    },
  ];

  if (debentures.isError) return <p className="type-body text-negative">Não foi possível carregar as debêntures.</p>;
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setEditing("nova")}>Nova debênture</Button>
      </div>
      <DataTable
        tableId="ajustes-debentures"
        caption="Debêntures"
        data={debentures.data ?? []}
        columns={columns}
        getRowId={(d) => d.id}
        empty={debentures.isLoading ? "Carregando…" : "Nenhuma debênture. Cadastre para valorar pela taxa."}
      />
      {(debentures.data ?? []).map((d) => (
        <ContributionsBlock key={d.id} debenture={d} />
      ))}
      {editing && (
        <DebentureForm
          key={editing === "nova" ? "nova" : editing.id}
          debenture={editing === "nova" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
