"use client";

// Ajustes › Metas (Story 8.2 — FR-35, UX-DR43): classe → ativo, com % da meta, banda (p.p.) e piso
// (R$) por classe. Cada nível precisa somar 100%: quem confere é a API (`POST
// /api/v1/planning/targets/preview` — o navegador não soma); senão "Soma em {x}%. Ajuste para 100%."
// e Salvar fica desabilitado. Salvar grava a versão das metas a partir do mês atual.
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { SAVE_FAILED } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatBRL, formatDate } from "@/lib/format";
import { useSaveTargets, useTargets, useTargetsPreview } from "@/lib/planning";
import { useDebounced } from "@/lib/use-debounced";
import type { TargetsIn, TargetsOut } from "@/types/planning";

type Draft = {
  cls: string;
  label: string;
  pct: string;
  band: string;
  floor: string;
  assets: { asset_id: string; label: string; pct: string }[];
}[];

const NUMBER = /^\d+([.,]\d{1,2})?$/;

function text(n: number): string {
  return String(n).replace(".", ",");
}

function toDraft(data: TargetsOut): Draft {
  return data.classes.map((c) => ({
    cls: c.cls,
    label: c.label,
    pct: text(c.pct),
    band: text(c.band_pp),
    floor: text(c.floor),
    assets: c.assets.map((a) => ({ asset_id: a.asset_id, label: a.label, pct: text(a.pct) })),
  }));
}

function money(raw: string): string {
  return raw.trim().replace(/\./g, "").replace(",", ".");
}

function toBody(draft: Draft): TargetsIn | null {
  const fields = draft.flatMap((c) => [c.pct, c.band, ...c.assets.map((a) => a.pct)]);
  if (fields.some((f) => !NUMBER.test(f.trim())) || draft.some((c) => !/^\d+(\.\d{1,2})?$/.test(money(c.floor)))) {
    return null;
  }
  const dot = (v: string) => v.trim().replace(",", ".");
  return {
    classes: draft.map((c) => ({
      cls: c.cls,
      pct: dot(c.pct),
      band_pp: dot(c.band),
      floor: money(c.floor),
      assets: c.assets.map((a) => ({ asset_id: a.asset_id, pct: dot(a.pct) })),
    })),
  };
}

function Editor({ data, onDone }: { data: TargetsOut; onDone: () => void }) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(data));
  const [open, setOpen] = useState<string | null>(null);
  const save = useSaveTargets();
  const body = toBody(draft);
  const debounced = useDebounced(body);
  const preview = useTargetsPreview(debounced);
  const errors = preview.data?.errors ?? [];
  const stale = JSON.stringify(debounced) !== JSON.stringify(body);
  const canSave = body !== null && !stale && preview.data?.ok === true && !save.isPending;

  const set = (i: number, patch: Partial<Draft[number]>) =>
    setDraft((cur) => cur.map((c, k) => (k === i ? { ...c, ...patch } : c)));
  const setAsset = (i: number, j: number, pct: string) =>
    setDraft((cur) =>
      cur.map((c, k) => (k === i ? { ...c, assets: c.assets.map((a, m) => (m === j ? { ...a, pct } : a)) } : c)),
    );

  const errorFor = (level: string) => errors.find((e) => e.level === level)?.message;
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSave || !body) return;
        save.mutate(body, {
          onSuccess: () => {
            toast("Metas salvas.");
            onDone();
          },
          onError: () => toast(SAVE_FAILED),
        });
      }}
    >
      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full type-body-sm">
          <caption className="sr-only">Metas por classe e por ativo</caption>
          <thead className="bg-muted text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 text-left font-medium">Classe / ativo</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Meta (%)</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Banda (p.p.)</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Piso (R$)</th>
            </tr>
          </thead>
          <tbody>
            {draft.map((c, i) => (
              <ClassRows
                key={c.cls}
                row={c}
                open={open === c.cls}
                onToggle={() => setOpen(open === c.cls ? null : c.cls)}
                onChange={(patch) => set(i, patch)}
                onAsset={(j, pct) => setAsset(i, j, pct)}
                error={errorFor(c.cls)}
              />
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p role="status" aria-live="polite" className="type-body-sm text-negative">
          {body === null ? "Use números (ex.: 12,5)." : errorFor("classes") ?? ""}
        </p>
        <span className="flex gap-2">
          <Button type="button" variant="secondary" onClick={onDone}>
            Cancelar
          </Button>
          <Button type="submit" disabled={!canSave}>
            Salvar
          </Button>
        </span>
      </div>
    </form>
  );
}

function ClassRows({
  row,
  open,
  onToggle,
  onChange,
  onAsset,
  error,
}: {
  row: Draft[number];
  open: boolean;
  onToggle: () => void;
  onChange: (patch: Partial<Draft[number]>) => void;
  onAsset: (j: number, pct: string) => void;
  error: string | undefined;
}) {
  const cell = "px-4 py-1.5 text-right";
  const input = "h-8 w-24 type-num-body text-right";
  return (
    <>
      <tr className="border-t border-border">
        <th scope="row" className="px-4 py-1.5 text-left font-medium">
          <button
            type="button"
            className="inline-flex items-center gap-1"
            aria-expanded={open}
            onClick={onToggle}
            disabled={!row.assets.length}
          >
            {row.assets.length ? open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" /> : null}
            {row.label}
          </button>
          {error && <span className="ml-2 type-caption text-negative">{error}</span>}
        </th>
        <td className={cell}>
          <Input aria-label={`Meta de ${row.label} (%)`} inputMode="decimal" className={input} value={row.pct} onChange={(e) => onChange({ pct: e.target.value })} />
        </td>
        <td className={cell}>
          <Input aria-label={`Banda de ${row.label} (p.p.)`} inputMode="decimal" className={input} value={row.band} onChange={(e) => onChange({ band: e.target.value })} />
        </td>
        <td className={cell}>
          <Input aria-label={`Piso de ${row.label} (R$)`} inputMode="decimal" className={input} value={row.floor} onChange={(e) => onChange({ floor: e.target.value })} />
        </td>
      </tr>
      {open &&
        row.assets.map((a, j) => (
          <tr key={a.asset_id} className="border-t border-border bg-muted/40">
            <th scope="row" className="py-1.5 pr-4 pl-10 text-left font-normal">
              {a.label}
            </th>
            <td className={cell}>
              <Input aria-label={`Meta de ${a.label} em ${row.label} (%)`} inputMode="decimal" className={input} value={a.pct} onChange={(e) => onAsset(j, e.target.value)} />
            </td>
            <td colSpan={2} className="px-4 py-1.5 type-caption text-muted-foreground">
              {j === 0 ? "dentro da classe; 0 em todos = sem meta por ativo" : null}
            </td>
          </tr>
        ))}
    </>
  );
}

export default function MetasPage() {
  const targets = useTargets();
  const [editing, setEditing] = useState(false);
  if (targets.isError) return <p className="type-body text-negative">Não foi possível carregar as metas.</p>;
  if (!targets.data) return <div className="h-48 animate-pulse rounded-lg border border-border bg-card" aria-hidden />;
  const data = targets.data;
  // chave fixa: a revalidação depois de salvar não pode remontar o editor (o onSuccess se perderia)
  if (editing) return <Editor key="editor" data={data} onDone={() => setEditing(false)} />;
  if (!data.defined) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card p-card-padding">
        <p className="type-body text-muted-foreground">Nenhuma meta. Sem metas, a distribuição do aporte não tem base.</p>
        <Button onClick={() => setEditing(true)}>Definir metas</Button>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="type-caption text-muted-foreground">
          {data.valid_from ? `vigentes desde ${formatDate(data.valid_from)}` : null}
        </span>
        <Button onClick={() => setEditing(true)}>Editar metas</Button>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full type-body-sm">
          <caption className="sr-only">Metas de alocação</caption>
          <thead className="bg-muted text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 text-left font-medium">Classe</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Meta</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Banda</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Piso</th>
              <th scope="col" className="px-4 py-2 text-left font-medium">Por ativo</th>
            </tr>
          </thead>
          <tbody>
            {data.classes.map((c) => {
              const withTarget = c.assets.filter((a) => a.pct > 0);
              return (
                <tr key={c.cls} className="border-t border-border">
                  <th scope="row" className="px-4 py-2 text-left font-normal">{c.label}</th>
                  <td className="px-4 py-2 text-right type-num-table">{text(c.pct)}%</td>
                  <td className="px-4 py-2 text-right type-num-table">± {text(c.band_pp)} p.p.</td>
                  <td className="px-4 py-2 text-right type-num-table">{formatBRL(c.floor)}</td>
                  <td className="px-4 py-2 type-caption text-muted-foreground">
                    {withTarget.length ? withTarget.map((a) => `${a.label} ${text(a.pct)}%`).join(" · ") : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
