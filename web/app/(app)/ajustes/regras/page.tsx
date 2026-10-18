"use client";

// Ajustes › Regras (Story 2.10 — FR-10, FR-11, FR-35, UX-DR43): regras "descrição contém" com direção,
// categoria e estado. Editar em Formulário em painel lateral com prévia das transações afetadas
// (`rules/preview`, não grava); desativar não mexe no que a regra já categorizou. Reaplicar a um
// período mostra antes × depois e nunca altera categoria manual.
import { useRef, useState } from "react";
import { toast } from "sonner";

import { ReapplyDiff } from "@/components/ajustes/ReapplyDiff";
import { CategoryCombobox } from "@/components/caixa/CategoryCombobox";
import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { StatusBadge } from "@/components/data/StatusBadge";
import { FormField, SAVE_FAILED, SideForm } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { formatDate, formatSignedBRL } from "@/lib/format";
import {
  useCategoryOptions,
  useReapplyPreview,
  useReapplyRules,
  useRulePreview,
  useRules,
  useUpdateRule,
} from "@/lib/ledger";
import { MIN_MONTH, currentMonthBRT } from "@/lib/period";
import { useDebounced } from "@/lib/use-debounced";
import type { CategoryOption, CategoryRule, RuleDirection } from "@/types/ledger";

const DIRECTION_LABEL: Record<RuleDirection, string> = {
  saida: "Saída",
  entrada: "Entrada",
  ambos: "Entrada e saída",
};

function RuleForm({ rule, options, onClose }: { rule: CategoryRule; options: CategoryOption[]; onClose: () => void }) {
  const update = useUpdateRule();
  const [pattern, setPattern] = useState(rule.pattern);
  const [direction, setDirection] = useState<RuleDirection>(rule.direction);
  const [category, setCategory] = useState<CategoryOption | null>(options.find((o) => o.id === rule.category_id) ?? null);
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);
  const preview = useRulePreview(useDebounced(pattern), direction);
  const patternError = pattern.trim() ? conflict : "Informe o texto da condição.";
  const dirty = pattern !== rule.pattern || direction !== rule.direction || category?.id !== rule.category_id;

  function submit() {
    setTouched(true);
    if (!pattern.trim() || !category) return;
    setFailed(false);
    setConflict(null);
    update.mutate(
      { id: rule.id, body: { pattern: pattern.trim(), direction, category_id: category.id } },
      {
        onSuccess: () => {
          toast("Regra salva.");
          onClose();
        },
        onError: (err) => {
          if (err instanceof ApiError && err.status === 409) setConflict(apiErrorMessage(err.detail, ""));
          else setFailed(true);
        },
      },
    );
  }

  return (
    <SideForm
      open
      title="Editar regra"
      description="Vale para as próximas transações; o histórico só muda ao reaplicar."
      dirty={dirty}
      saving={update.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      <FormField id="regra-condicao" label="Descrição contém" error={touched ? patternError : null}>
        <Input
          id="regra-condicao"
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
          onBlur={() => setTouched(true)}
          aria-invalid={Boolean(touched && patternError)}
        />
      </FormField>
      <FormField id="regra-direcao" label="Direção">
        <select
          id="regra-direcao"
          value={direction}
          onChange={(e) => setDirection(e.target.value as RuleDirection)}
          className="h-9 w-full rounded-md border border-input bg-background px-3 type-body"
        >
          {(Object.keys(DIRECTION_LABEL) as RuleDirection[]).map((d) => (
            <option key={d} value={d}>
              {DIRECTION_LABEL[d]}
            </option>
          ))}
        </select>
      </FormField>
      <FormField id="regra-categoria" label="Categoria" error={touched && !category ? "Escolha a categoria." : null}>
        <CategoryCombobox
          options={options}
          value={category?.id ?? null}
          label={category?.label ?? "Escolha a categoria"}
          empty={!category}
          onSelect={setCategory}
        />
      </FormField>
      <div className="space-y-1.5" aria-live="polite">
        <p className="type-body-sm font-semibold">
          {pattern.trim()
            ? `${preview.data?.total ?? 0} ${preview.data?.total === 1 ? "transação bate" : "transações batem"} com a condição`
            : "Digite a condição para ver as transações"}
        </p>
        <ul className="max-h-64 space-y-1 overflow-y-auto type-body-sm">
          {pattern.trim() &&
            preview.data?.items.map((m) => (
              <li key={m.id} className="flex justify-between gap-2 border-t border-border pt-1">
                <span className="min-w-0 truncate">
                  {formatDate(m.date)} · {m.description ?? "—"}
                  <span className="block text-muted-foreground">{m.category_label}</span>
                </span>
                <span className="type-num-table whitespace-nowrap">{formatSignedBRL(m.amount)}</span>
              </li>
            ))}
        </ul>
      </div>
    </SideForm>
  );
}

function ReapplySection() {
  const current = currentMonthBRT();
  const [de, setDe] = useState(current);
  const [ate, setAte] = useState(current);
  const preview = useReapplyPreview();
  const reapply = useReapplyRules();
  const invalid = !de || !ate || de > ate;

  const ask = () => preview.mutate({ de, ate });
  const confirm = () =>
    reapply.mutate(
      { de, ate },
      {
        onSuccess: ({ changed }) => {
          toast(changed === 1 ? "1 transação recategorizada." : `${changed} transações recategorizadas.`);
          preview.reset();
        },
        onError: () => toast(SAVE_FAILED),
      },
    );

  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-card-padding" aria-labelledby="reaplicar">
      <div>
        <h2 id="reaplicar" className="type-section-title">
          Reaplicar regras ao histórico
        </h2>
        <p className="type-body-sm text-muted-foreground">
          Passa as regras ativas de novo pelas transações do período. Categorias que você escolheu à mão ficam.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <FormField id="reaplicar-de" label="De">
          <Input id="reaplicar-de" type="month" min={MIN_MONTH} max={current} value={de} onChange={(e) => { setDe(e.target.value); preview.reset(); }} />
        </FormField>
        <FormField id="reaplicar-ate" label="Até" error={de > ate ? "O fim vem antes do início." : null}>
          <Input id="reaplicar-ate" type="month" min={MIN_MONTH} max={current} value={ate} onChange={(e) => { setAte(e.target.value); preview.reset(); }} />
        </FormField>
        <Button variant="secondary" disabled={invalid || preview.isPending} onClick={ask}>
          Ver prévia
        </Button>
      </div>
      {preview.isError && <p className="type-body-sm text-negative">Não foi possível montar a prévia.</p>}
      {preview.data && (
        <>
          <ReapplyDiff preview={preview.data} />
          {preview.data.changes.length > 0 && (
            <Button disabled={reapply.isPending} onClick={confirm}>
              Reaplicar a {preview.data.changes.length} {preview.data.changes.length === 1 ? "transação" : "transações"}
            </Button>
          )}
        </>
      )}
    </section>
  );
}

export default function RegrasPage() {
  const rules = useRules();
  const options = useCategoryOptions();
  const update = useUpdateRule();
  const [editing, setEditingState] = useState<CategoryRule | null>(null);
  // O painel abre por estado: guarda quem abriu e devolve o foco a ele ao fechar (UX-DR43).
  const opener = useRef<HTMLElement | null>(null);
  const setEditing = (next: CategoryRule | null) => {
    if (next) opener.current = document.activeElement as HTMLElement | null;
    setEditingState(next);
    if (!next) requestAnimationFrame(() => opener.current?.focus());
  };

  const toggle = (r: CategoryRule) =>
    update.mutate(
      { id: r.id, body: { is_active: !r.is_active } },
      {
        onSuccess: () => toast(r.is_active ? "Regra desativada. O que ela já categorizou fica." : "Regra reativada."),
        onError: () => toast(SAVE_FAILED),
      },
    );

  const columns: DataColumn<CategoryRule>[] = [
    {
      id: "condicao",
      header: "Condição",
      value: (r) => r.pattern,
      cell: (r) => (
        <span className={r.is_active ? undefined : "text-muted-foreground"}>
          descrição contém “{r.pattern}”
        </span>
      ),
    },
    { id: "direcao", header: "Direção", value: (r) => DIRECTION_LABEL[r.direction] },
    { id: "categoria", header: "Categoria", value: (r) => r.category_label },
    {
      id: "estado",
      header: "Estado",
      value: (r) => (r.is_active ? "ativa" : "inativa"),
      cell: (r) => <StatusBadge tone={r.is_active ? undefined : "warning"}>{r.is_active ? "ativa" : "inativa"}</StatusBadge>,
    },
    { id: "origem", header: "Origem", value: (r) => r.origin, detailOnly: true },
    {
      id: "acoes",
      header: "Ações",
      value: () => null,
      sortable: false,
      cell: (r) => (
        <span className="inline-flex gap-3">
          <button type="button" className="text-positive underline" onClick={() => setEditing(r)}>
            Editar
          </button>
          <button type="button" className="text-positive underline" onClick={() => toggle(r)}>
            {r.is_active ? "Desativar" : "Reativar"}
          </button>
        </span>
      ),
    },
  ];

  if (rules.isError) return <p className="type-body text-negative">Não foi possível carregar as regras.</p>;

  return (
    <div className="space-y-section-gap">
      <DataTable
        tableId="ajustes-regras"
        caption="Regras de categoria"
        data={rules.data ?? []}
        columns={columns}
        getRowId={(r) => r.id}
        empty={rules.isLoading ? "Carregando…" : "Nenhuma regra. Regras nascem na revisão quando você corrige uma categoria."}
      />
      <ReapplySection />
      {editing && (
        <RuleForm key={editing.id} rule={editing} options={options.data ?? []} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}
