"use client";

// Ajustes › Objetivos (Story 8.1 — FR-17, FR-35, UX-DR43): nome, valor-alvo, prazo e as caixinhas
// vinculadas. A reserva de emergência é fixa: alvo = multiplicador × custos fixos (padrão 6), com
// horizonte editável (padrão 12 meses). A caixinha ainda não ligada é sugerida e o vínculo só vale
// confirmado. Progresso = valor atual dos ativos vinculados, com o aportado ao lado (tudo da API).
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
import { formatBRL, formatDate, formatPercent, normalizeMoneyInput } from "@/lib/format";
import {
  useDeleteGoal,
  useDismissGoalSuggestion,
  useGoals,
  useLinkGoalAsset,
  useSaveGoal,
} from "@/lib/planning";
import type { Goal, GoalAsset, GoalSuggestion } from "@/types/planning";

type Editing = Goal | { kind: "novo"; name: string; assetIds: string[] };

function moneyText(v: number): string {
  return String(Number(v).toFixed(2)).replace(".", ",");
}

function GoalForm({
  editing,
  free,
  onClose,
}: {
  editing: Editing;
  free: GoalSuggestion[];
  onClose: () => void;
}) {
  const save = useSaveGoal();
  const goal = editing.kind === "novo" ? null : editing;
  const reserve = goal?.kind === "reserva";
  const [name, setName] = useState(goal?.name ?? (editing.kind === "novo" ? editing.name : ""));
  const [target, setTarget] = useState(goal && !reserve ? moneyText(goal.target) : "");
  const [deadline, setDeadline] = useState(goal?.deadline ?? "");
  const [multiplier, setMultiplier] = useState(goal?.multiplier ? String(goal.multiplier).replace(".", ",") : "6");
  const [horizon, setHorizon] = useState(String(goal?.horizon_months ?? 12));
  const initialAssets = goal ? goal.assets.map((a) => a.asset_id) : editing.kind === "novo" ? editing.assetIds : [];
  const [assets, setAssets] = useState<string[]>(initialAssets);
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const options: { asset_id: string; label: string }[] = [...(goal?.assets ?? []), ...free];
  const targetValue = normalizeMoneyInput(target);
  const multiplierValue = multiplier.trim().replace(",", ".");
  const errors: Record<string, string | null> = reserve
    ? {
        multiplier: /^\d+(\.\d{1,2})?$/.test(multiplierValue) && Number(multiplierValue) > 0 ? null : "Informe o multiplicador (ex.: 6).",
        horizon: /^\d+$/.test(horizon) && Number(horizon) > 0 ? null : "Informe o horizonte em meses.",
      }
    : {
        name: name.trim() ? null : "Informe o nome.",
        target: targetValue !== null && Number(targetValue) > 0 ? null : "Informe o valor-alvo (ex.: 5.000,00).",
        deadline: /^\d{4}-\d{2}-\d{2}$/.test(deadline) ? null : "Informe o prazo.",
      };
  const dirty =
    name !== (goal?.name ?? "") ||
    target !== (goal && !reserve ? moneyText(goal.target) : "") ||
    deadline !== (goal?.deadline ?? "") ||
    assets.join() !== initialAssets.join() ||
    (reserve && (multiplier !== String(goal?.multiplier).replace(".", ",") || horizon !== String(goal?.horizon_months)));

  function toggle(id: string) {
    setAssets((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  function submit() {
    setTouched(true);
    if (Object.values(errors).some(Boolean)) return;
    setFailed(false);
    const body = reserve
      ? { multiplier: multiplierValue, horizon_months: Number(horizon), asset_ids: assets }
      : { name: name.trim(), target: targetValue ?? undefined, deadline, asset_ids: assets };
    save.mutate(
      { id: goal?.id ?? null, body },
      {
        onSuccess: () => {
          toast(goal ? "Objetivo salvo." : "Objetivo criado.");
          onClose();
        },
        onError: () => setFailed(true),
      },
    );
  }

  const shown = (k: string) => (touched ? errors[k] : null);
  return (
    <SideForm
      open
      title={reserve ? "Reserva de emergência" : goal ? "Editar objetivo" : "Novo objetivo"}
      description={
        reserve
          ? "Alvo = multiplicador × custos fixos do mês; o horizonte divide o que falta na distribuição do aporte."
          : "O progresso é o valor atual das caixinhas vinculadas."
      }
      dirty={Boolean(dirty)}
      saving={save.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      {reserve ? (
        <>
          <FormField id="obj-mult" label="Multiplicador dos custos fixos" error={shown("multiplier")}>
            <Input
              id="obj-mult"
              inputMode="decimal"
              value={multiplier}
              onChange={(e) => setMultiplier(e.target.value)}
              className="type-num-body w-24"
            />
          </FormField>
          <FormField id="obj-horizonte" label="Horizonte (meses)" error={shown("horizon")}>
            <Input
              id="obj-horizonte"
              inputMode="numeric"
              value={horizon}
              onChange={(e) => setHorizon(e.target.value)}
              className="type-num-body w-24"
            />
          </FormField>
        </>
      ) : (
        <>
          <FormField id="obj-nome" label="Nome" error={shown("name")}>
            <Input id="obj-nome" value={name} onChange={(e) => setName(e.target.value)} />
          </FormField>
          <FormField id="obj-alvo" label="Valor-alvo" error={shown("target")}>
            <Input
              id="obj-alvo"
              inputMode="decimal"
              value={target}
              placeholder="5.000,00"
              onChange={(e) => setTarget(e.target.value)}
              className="type-num-body w-40"
            />
          </FormField>
          <FormField id="obj-prazo" label="Prazo" error={shown("deadline")}>
            <Input id="obj-prazo" type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="w-44" />
          </FormField>
        </>
      )}
      <fieldset className="space-y-1">
        <legend className="type-label">Caixinhas vinculadas</legend>
        {options.length === 0 ? (
          <p className="type-caption text-muted-foreground">Nenhuma caixinha livre para vincular.</p>
        ) : (
          options.map((o) => (
            <label key={o.asset_id} className="flex items-center gap-2 type-body-sm">
              <input type="checkbox" checked={assets.includes(o.asset_id)} onChange={() => toggle(o.asset_id)} />
              {o.label}
            </label>
          ))
        )}
      </fieldset>
    </SideForm>
  );
}

function Suggestions({
  suggestions,
  goals,
  onCreate,
}: {
  suggestions: GoalSuggestion[];
  goals: Goal[];
  onCreate: (s: GoalSuggestion) => void;
}) {
  const link = useLinkGoalAsset();
  const dismiss = useDismissGoalSuggestion();
  const busy = link.isPending || dismiss.isPending;
  if (!suggestions.length) return null;
  return (
    <section aria-labelledby="obj-sugestoes" className="space-y-2 rounded-lg border border-border bg-card shadow-card p-card-padding">
      <h2 id="obj-sugestoes" className="type-section-title">
        Caixinhas sem objetivo
      </h2>
      <ul className="space-y-2">
        {suggestions.map((s) => (
          <li key={s.asset_id} className="flex flex-wrap items-center justify-between gap-2 type-body-sm">
            <span>{s.label} ainda não está ligada a um objetivo.</span>
            <span className="flex flex-wrap items-center gap-2">
              {s.goal_id ? (
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={() =>
                    s.goal_id &&
                    link.mutate(
                      { goalId: s.goal_id, assetId: s.asset_id },
                      { onSuccess: () => toast(`${s.label} ligada a ${s.goal_name}.`), onError: () => toast(SAVE_FAILED) },
                    )
                  }
                >
                  Ligar a {s.goal_name}
                </Button>
              ) : (
                goals.length > 0 && (
                  <select
                    aria-label={`Ligar ${s.label} a um objetivo`}
                    className="h-8 rounded-md border border-input bg-background px-2 type-body-sm"
                    value=""
                    disabled={busy}
                    onChange={(e) => {
                      const goal = goals.find((g) => g.id === e.target.value);
                      if (goal)
                        link.mutate(
                          { goalId: goal.id, assetId: s.asset_id },
                          { onSuccess: () => toast(`${s.label} ligada a ${goal.name}.`), onError: () => toast(SAVE_FAILED) },
                        );
                    }}
                  >
                    <option value="">Ligar a…</option>
                    {goals.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                )
              )}
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => onCreate(s)}>
                Novo objetivo
              </Button>
              <button
                type="button"
                className="text-positive underline disabled:opacity-50"
                disabled={busy}
                onClick={() =>
                  dismiss.mutate(s.asset_id, {
                    onSuccess: () => toast(`${s.label} não é objetivo.`),
                    onError: () => toast(SAVE_FAILED),
                  })
                }
              >
                Não é objetivo
              </button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function assetsText(assets: GoalAsset[]): string {
  return assets.length ? assets.map((a) => a.label).join(", ") : "—";
}

export default function ObjetivosPage() {
  const data = useGoals();
  const remove = useDeleteGoal();
  const [editing, setEditingState] = useState<Editing | null>(null);
  const [deleting, setDeleting] = useState<Goal | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const setEditing = (next: Editing | null) => {
    if (next) opener.current = document.activeElement as HTMLElement | null;
    setEditingState(next);
    if (!next) requestAnimationFrame(() => opener.current?.focus());
  };

  const goals = data.data?.goals ?? [];
  const suggestions = data.data?.suggestions ?? [];
  const columns: DataColumn<Goal>[] = [
    { id: "nome", header: "Objetivo", value: (g) => g.name },
    {
      id: "alvo",
      header: "Alvo",
      value: (g) => g.target,
      numeric: true,
      cell: (g) =>
        g.kind === "reserva" ? (
          <span title={`${String(g.multiplier).replace(".", ",")}× os custos fixos do mês`}>
            {formatBRL(g.target)} <span className="type-caption text-muted-foreground">({String(g.multiplier).replace(".", ",")}× custos fixos)</span>
          </span>
        ) : (
          formatBRL(g.target)
        ),
    },
    {
      id: "prazo",
      header: "Prazo",
      value: (g) => g.deadline,
      cell: (g) => (g.kind === "reserva" ? `horizonte de ${g.horizon_months} meses` : g.deadline ? formatDate(g.deadline) : "—"),
    },
    { id: "ativos", header: "Caixinhas", value: (g) => assetsText(g.assets), sortable: false },
    { id: "valor", header: "Valor atual", value: (g) => g.valor, numeric: true, cell: (g) => formatBRL(g.valor) },
    { id: "aportado", header: "Aportado", value: (g) => g.aportado, numeric: true, cell: (g) => formatBRL(g.aportado) },
    { id: "progresso", header: "Progresso", value: (g) => g.progress, numeric: true, cell: (g) => formatPercent(g.progress) },
    {
      id: "acoes",
      header: "Ações",
      value: () => null,
      sortable: false,
      actions: true,
      cell: (g) => (
        <RowActions
          subject={g.name}
          onEdit={() => setEditing(g)}
          onDelete={g.kind !== "reserva" ? () => setDeleting(g) : undefined}
        />
      ),
    },
  ];

  if (data.isError && !data.data) return <p className="type-body text-negative">Não foi possível carregar os objetivos.</p>;
  return (
    <div className="space-y-3">
      <Suggestions
        suggestions={suggestions}
        goals={goals}
        onCreate={(s) => setEditing({ kind: "novo", name: s.label.replace(/^Caixinha /, ""), assetIds: [s.asset_id] })}
      />
      <div className="flex justify-end">
        <Button onClick={() => setEditing({ kind: "novo", name: "", assetIds: [] })}>Novo objetivo</Button>
      </div>
      <DataTable
        tableId="ajustes-objetivos"
        caption="Objetivos"
        data={goals}
        columns={columns}
        getRowId={(g) => g.id}
        empty={data.isLoading ? "Carregando…" : "Nenhum objetivo além da reserva de emergência."}
      />
      {!data.isLoading && goals.length === 1 && (
        <p className="type-body-sm text-muted-foreground">Nenhum objetivo além da reserva de emergência.</p>
      )}
      {editing && (
        <GoalForm
          key={editing.kind === "novo" ? `novo-${editing.assetIds.join()}` : editing.id}
          editing={editing}
          free={suggestions}
          onClose={() => setEditing(null)}
        />
      )}
      <AlertDialog open={deleting !== null} onOpenChange={(v) => (v ? undefined : setDeleting(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir {deleting?.name}?</AlertDialogTitle>
            <AlertDialogDescription>As caixinhas vinculadas voltam a ser sugeridas.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel autoFocus>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleting &&
                remove.mutate(deleting.id, {
                  onSuccess: () => toast("Objetivo excluído."),
                  onError: () => toast(SAVE_FAILED),
                })
              }
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
