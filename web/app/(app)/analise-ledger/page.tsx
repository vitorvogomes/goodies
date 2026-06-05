"use client";

// STORY-01-15 — Análise do ledger: (1) receitas/despesas por categoria com seletor
// de mês, (2) gestão de categorias inline, (3) custos recorrentes (CRUD inline).
// Reusa primitivos de ui.tsx + barras CSS (sem libs de chart), como o dashboard.
import { useState } from "react";

import { Button, Card, Input, Select } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { formatBRL, formatMonth, formatPercent } from "@/lib/format";
import {
  useCategories,
  useCategoryBreakdown,
  useCreateCategory,
  useCreateFixedCost,
  useDeleteCategory,
  useDeleteFixedCost,
  useFixedCosts,
  useMonthlySummaries,
  useUpdateCategory,
  useUpdateFixedCost,
} from "@/lib/ledger";
import type {
  Category,
  CategoryBreakdownRow,
  CategoryKind,
  CategoryUpdate,
  FixedCost,
  FixedCostCreate,
} from "@/types/ledger";

const KINDS: CategoryKind[] = ["income", "expense", "investment", "transfer"];
const KIND_LABELS: Record<CategoryKind, string> = {
  income: "Receita",
  expense: "Despesa",
  investment: "Investimento",
  transfer: "Transferência",
};

const INLINE_INPUT =
  "w-full rounded border border-accent/40 bg-background px-1.5 py-1 text-foreground outline-none";

// ---------------------------------------------------------------- Breakdown

type Tone = "gain" | "loss" | "invest";

function BreakdownRow({ row, tone }: { row: CategoryBreakdownRow; tone: Tone }) {
  const bar = tone === "gain" ? "bg-gain/70" : tone === "loss" ? "bg-loss/70" : "bg-accent/70";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-foreground/80">{row.category}</span>
        <span className="tabular-nums text-foreground/60">
          {formatBRL(row.total)} · {formatPercent(row.pct)}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full ${bar}`}
          style={{ width: `${Math.min(100, row.pct)}%` }}
        />
      </div>
    </div>
  );
}

function BreakdownSection({
  title,
  rows,
  total,
  tone,
  note,
}: {
  title: string;
  rows: CategoryBreakdownRow[];
  total: number;
  tone: Tone;
  note?: string;
}) {
  const totalColor =
    tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-accent";
  return (
    <Card>
      <div className="mb-4 flex items-baseline justify-between">
        <p className="text-sm text-foreground/50">{title}</p>
        <p className={`text-sm font-semibold tabular-nums ${totalColor}`}>{formatBRL(total)}</p>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-foreground/40">Sem lançamentos no período.</p>
      ) : (
        <div className="space-y-3">
          {rows.map((r) => (
            <BreakdownRow key={r.category} row={r} tone={tone} />
          ))}
        </div>
      )}
      {note && <p className="mt-4 text-xs italic text-foreground/40">{note}</p>}
    </Card>
  );
}

function CategoryBreakdownCard() {
  const summaries = useMonthlySummaries();
  const months = (summaries.data ?? []).map((m) => m.month);
  // null = padrão (mês mais recente); "" = Tudo (acumulado); "YYYY-MM" = mês escolhido.
  const [monthSel, setMonthSel] = useState<string | null>(null);
  const effectiveMonth = monthSel ?? months[0] ?? "";

  const breakdown = useCategoryBreakdown(effectiveMonth || undefined);
  const data = breakdown.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">Por categoria</h2>
        <div className="w-52">
          <Select value={effectiveMonth} onChange={(e) => setMonthSel(e.target.value)}>
            <option value="">Tudo (acumulado)</option>
            {months.map((m) => (
              <option key={m} value={m}>
                {formatMonth(m)}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {breakdown.isLoading && <p className="text-foreground/50">Carregando…</p>}
      {breakdown.isError && <p className="text-loss">Erro ao carregar o breakdown.</p>}
      {data && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <BreakdownSection
            title="Receitas"
            rows={data.income}
            total={data.income_total}
            tone="gain"
          />
          <BreakdownSection
            title="Gastos (consumo)"
            rows={data.expense}
            total={data.expense_total}
            tone="loss"
            note="Só consumo entra na taxa de poupança. Transferências internas ficam de fora."
          />
          <BreakdownSection
            title="Investimentos"
            rows={data.investment}
            total={data.investment_total}
            tone="invest"
            note="Saem do saldo mas não são consumo. O ativo é detalhado no Portfolio (m2)."
          />
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------- Categorias

function CategoryRow({
  cat,
  onUpdate,
  onDelete,
}: {
  cat: Category;
  onUpdate: (id: string, patch: CategoryUpdate) => void;
  onDelete: (id: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(cat.name);
  const [editingPat, setEditingPat] = useState(false);
  const [patDraft, setPatDraft] = useState("");

  function commitName() {
    setEditing(false);
    const v = draft.trim();
    if (v && v !== cat.name) onUpdate(cat.id, { name: v });
  }

  function commitPatterns() {
    setEditingPat(false);
    const next = patDraft.split(",").map((s) => s.trim()).filter(Boolean);
    if (next.join("|") !== cat.match_patterns.join("|"))
      onUpdate(cat.id, { match_patterns: next });
  }

  return (
    <tr className="border-t border-border">
      <td className="px-3 py-2 text-foreground/80">
        {editing ? (
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitName}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitName();
              if (e.key === "Escape") {
                setDraft(cat.name);
                setEditing(false);
              }
            }}
            className={INLINE_INPUT}
          />
        ) : (
          <button
            type="button"
            onClick={() => {
              setDraft(cat.name);
              setEditing(true);
            }}
            className="cursor-text text-left hover:text-foreground"
          >
            {cat.name}
          </button>
        )}
      </td>
      <td className="px-3 py-2">
        <select
          value={cat.kind}
          onChange={(e) => onUpdate(cat.id, { kind: e.target.value as CategoryKind })}
          className="cursor-pointer rounded border-0 bg-transparent py-0.5 text-foreground/60 outline-none hover:text-foreground focus:ring-1 focus:ring-accent/40"
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {KIND_LABELS[k]}
            </option>
          ))}
        </select>
      </td>
      <td className="px-3 py-2">
        {editingPat ? (
          <input
            autoFocus
            value={patDraft}
            onChange={(e) => setPatDraft(e.target.value)}
            onBlur={commitPatterns}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitPatterns();
              if (e.key === "Escape") setEditingPat(false);
            }}
            placeholder="rdb, corretora, ..."
            className={INLINE_INPUT}
          />
        ) : (
          <button
            type="button"
            onClick={() => {
              setPatDraft(cat.match_patterns.join(", "));
              setEditingPat(true);
            }}
            className="cursor-text text-left text-xs text-foreground/50 hover:text-foreground"
          >
            {cat.match_patterns.length ? cat.match_patterns.join(", ") : "—"}
          </button>
        )}
      </td>
      <td className="px-3 py-2">
        <button
          type="button"
          onClick={() => onUpdate(cat.id, { is_active: !cat.is_active })}
          className={
            cat.is_active
              ? "rounded-full bg-gain/15 px-2 py-0.5 text-xs text-gain"
              : "rounded-full bg-muted px-2 py-0.5 text-xs text-foreground/40"
          }
        >
          {cat.is_active ? "Ativa" : "Inativa"}
        </button>
      </td>
      <td className="px-3 py-2 text-right">
        <button
          type="button"
          onClick={() => onDelete(cat.id)}
          aria-label="Excluir categoria"
          className="text-foreground/30 hover:text-loss"
        >
          ✕
        </button>
      </td>
    </tr>
  );
}

function CategoryManager() {
  const categories = useCategories();
  const create = useCreateCategory();
  const update = useUpdateCategory();
  const del = useDeleteCategory();

  const [name, setName] = useState("");
  const [kind, setKind] = useState<CategoryKind>("expense");
  const [patterns, setPatterns] = useState("");
  const [error, setError] = useState<string | null>(null);

  function add() {
    const trimmed = name.trim();
    if (!trimmed) return;
    setError(null);
    const match_patterns = patterns.split(",").map((s) => s.trim()).filter(Boolean);
    create.mutate(
      { name: trimmed, kind, match_patterns },
      {
        onSuccess: () => {
          setName("");
          setPatterns("");
        },
        onError: (e) =>
          setError(
            e instanceof ApiError && e.status === 409
              ? "Já existe uma categoria com esse nome."
              : "Erro ao criar categoria.",
          ),
      },
    );
  }

  const items = categories.data ?? [];

  return (
    <Card>
      <h2 className="mb-4 text-lg font-semibold text-foreground">Categorias</h2>

      <div className="mb-4 flex flex-wrap items-end gap-2">
        <Input
          placeholder="Nova categoria"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") add();
          }}
          className="max-w-xs"
        />
        <div className="w-44">
          <Select value={kind} onChange={(e) => setKind(e.target.value as CategoryKind)}>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {KIND_LABELS[k]}
              </option>
            ))}
          </Select>
        </div>
        <Input
          placeholder="Padrões (auto-import): rdb, corretora…"
          value={patterns}
          onChange={(e) => setPatterns(e.target.value)}
          className="max-w-xs"
        />
        <Button onClick={add} disabled={create.isPending}>
          Adicionar
        </Button>
      </div>
      {error && <p className="mb-3 text-sm text-loss">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-foreground/60">
            <tr>
              <th className="px-3 py-2 font-medium">Nome</th>
              <th className="px-3 py-2 font-medium">Tipo</th>
              <th className="px-3 py-2 font-medium">Padrões (auto-import)</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-foreground/40">
                  Nenhuma categoria.
                </td>
              </tr>
            )}
            {items.map((cat) => (
              <CategoryRow
                key={cat.id}
                cat={cat}
                onUpdate={(id, patch) => update.mutate({ id, patch })}
                onDelete={(id) => del.mutate(id)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ----------------------------------------------------------- Custos fixos

function FixedCostRow({
  fc,
  categoryNames,
  onSave,
  onDelete,
}: {
  fc: FixedCost;
  categoryNames: string[];
  onSave: (id: string, patch: Partial<FixedCostCreate>) => void;
  onDelete: (id: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(fc.name);
  const [amount, setAmount] = useState(String(fc.amount));
  const [dueDay, setDueDay] = useState(String(fc.due_day));
  const [category, setCategory] = useState(fc.category);

  function save() {
    const parsedAmount = parseFloat(amount);
    const parsedDay = parseInt(dueDay, 10);
    if (!name.trim() || Number.isNaN(parsedAmount) || Number.isNaN(parsedDay)) return;
    onSave(fc.id, {
      name: name.trim(),
      amount: parsedAmount,
      due_day: parsedDay,
      category,
    });
    setEditing(false);
  }

  function cancel() {
    setName(fc.name);
    setAmount(String(fc.amount));
    setDueDay(String(fc.due_day));
    setCategory(fc.category);
    setEditing(false);
  }

  const options = categoryNames.includes(category) ? categoryNames : [category, ...categoryNames];

  if (editing) {
    return (
      <tr className="border-t border-border">
        <td className="px-3 py-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={INLINE_INPUT}
          />
        </td>
        <td className="px-3 py-2">
          <input
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className={INLINE_INPUT}
          />
        </td>
        <td className="px-3 py-2">
          <input
            type="number"
            min={1}
            max={31}
            value={dueDay}
            onChange={(e) => setDueDay(e.target.value)}
            className={INLINE_INPUT}
          />
        </td>
        <td className="px-3 py-2">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className={INLINE_INPUT}
          >
            {options.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </td>
        <td className="space-x-3 px-3 py-2 text-right">
          <button type="button" onClick={save} className="text-sm text-accent hover:underline">
            Salvar
          </button>
          <button
            type="button"
            onClick={cancel}
            className="text-sm text-foreground/50 hover:text-foreground"
          >
            Cancelar
          </button>
        </td>
      </tr>
    );
  }

  return (
    <tr className="border-t border-border">
      <td className="px-3 py-2 text-foreground/80">{fc.name}</td>
      <td className="px-3 py-2 tabular-nums text-foreground/80">{formatBRL(fc.amount)}</td>
      <td className="px-3 py-2 text-foreground/60">dia {fc.due_day}</td>
      <td className="px-3 py-2 text-foreground/60">{fc.category}</td>
      <td className="space-x-3 px-3 py-2 text-right">
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="text-sm text-foreground/50 hover:text-foreground"
        >
          Editar
        </button>
        <button
          type="button"
          onClick={() => onDelete(fc.id)}
          aria-label="Excluir custo fixo"
          className="text-foreground/30 hover:text-loss"
        >
          ✕
        </button>
      </td>
    </tr>
  );
}

function FixedCostsView() {
  const fixedCosts = useFixedCosts();
  const categories = useCategories();
  const create = useCreateFixedCost();
  const update = useUpdateFixedCost();
  const del = useDeleteFixedCost();

  const items = fixedCosts.data ?? [];
  const total = items.filter((f) => f.is_active).reduce((sum, f) => sum + f.amount, 0);
  const categoryNames = (categories.data ?? [])
    .filter((c) => c.kind === "expense" || c.kind === "investment")
    .map((c) => c.name);

  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [dueDay, setDueDay] = useState("");
  const [category, setCategory] = useState("");

  function add() {
    const parsedAmount = parseFloat(amount);
    const parsedDay = parseInt(dueDay, 10);
    const cat = category || categoryNames[0] || "";
    if (!name.trim() || Number.isNaN(parsedAmount) || Number.isNaN(parsedDay) || !cat) return;
    create.mutate(
      { name: name.trim(), amount: parsedAmount, due_day: parsedDay, category: cat },
      {
        onSuccess: () => {
          setName("");
          setAmount("");
          setDueDay("");
          setCategory("");
        },
      },
    );
  }

  return (
    <Card>
      <h2 className="mb-4 text-lg font-semibold text-foreground">Custos recorrentes</h2>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <Input placeholder="Nome" value={name} onChange={(e) => setName(e.target.value)} />
        <Input
          type="number"
          step="0.01"
          placeholder="Valor"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <Input
          type="number"
          min={1}
          max={31}
          placeholder="Dia"
          value={dueDay}
          onChange={(e) => setDueDay(e.target.value)}
        />
        <Select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Categoria…</option>
          {categoryNames.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
        <Button onClick={add} disabled={create.isPending}>
          Adicionar
        </Button>
      </div>

      <div className="overflow-hidden rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-foreground/60">
            <tr>
              <th className="px-3 py-2 font-medium">Nome</th>
              <th className="px-3 py-2 font-medium">Valor</th>
              <th className="px-3 py-2 font-medium">Pagamento</th>
              <th className="px-3 py-2 font-medium">Categoria</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-foreground/40">
                  Nenhum custo recorrente cadastrado.
                </td>
              </tr>
            )}
            {items.map((fc) => (
              <FixedCostRow
                key={fc.id}
                fc={fc}
                categoryNames={categoryNames}
                onSave={(id, patch) => update.mutate({ id, patch })}
                onDelete={(id) => del.mutate(id)}
              />
            ))}
          </tbody>
          {items.length > 0 && (
            <tfoot className="border-t border-border bg-muted/30 text-foreground/80">
              <tr>
                <td className="px-3 py-2 font-medium">Total mensal</td>
                <td className="px-3 py-2 font-semibold tabular-nums">{formatBRL(total)}</td>
                <td colSpan={3} />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </Card>
  );
}

// ----------------------------------------------------------------- Página

export default function AnaliseLedgerPage() {
  return (
    <div className="space-y-8">
      <h1 className="font-mono text-2xl font-semibold text-foreground">Análise</h1>
      <CategoryBreakdownCard />
      <CategoryManager />
      <FixedCostsView />
    </div>
  );
}
