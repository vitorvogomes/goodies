"use client";

// Ajustes › Categorias (Story 2.9 — FR-8, FR-35, UX-DR20, UX-DR43): árvore grupo › subcategoria com
// tipo de movimento e role. Arquivadas ocultas ("Mostrar arquivadas" as esmaece). Criar e editar em
// Formulário em painel lateral; categoria com transações só arquiva; renome avisa que reflete em todo
// o histórico; o tipo de um grupo com transações não muda.
import { ArchiveIcon, ArchiveRestoreIcon, PlusIcon } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { RowActions } from "@/components/data/RowActions";
import { StatusBadge } from "@/components/data/StatusBadge";
import { FormField, SideForm } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { useCategoryMutation, useCategoryTree } from "@/lib/ledger";
import { cn } from "@/lib/utils";
import type { CategoryGroupNode, CategoryNode, GroupKind } from "@/types/ledger";

const KIND_LABEL: Record<GroupKind, string> = {
  income: "Receita",
  expense: "Gasto",
  investment: "Investimento",
  transfer: "Transferência",
};
const ROLES: Record<GroupKind, Array<[string, string]>> = {
  income: [
    ["work_income", "Receita do trabalho"],
    ["resgate", "Resgate"],
    ["devolucao", "Devolução"],
  ],
  expense: [
    ["consumo", "Consumo"],
    ["divida", "Dívida"],
  ],
  investment: [["investimento", "Investimento"]],
  transfer: [["transferencia", "Transferência"]],
};
const DEFAULT_ROLE: Record<GroupKind, string> = {
  income: "work_income",
  expense: "consumo",
  investment: "investimento",
  transfer: "transferencia",
};

type Editing =
  | { type: "category"; node: CategoryNode | null; groupId?: string }
  | { type: "group"; node: CategoryGroupNode | null }
  | null;

function errorText(err: unknown): string | null {
  return err instanceof ApiError && err.status === 409 ? apiErrorMessage(err.detail, "") : null;
}

function CategoryForm({
  node,
  groupId,
  groups,
  onClose,
}: {
  node: CategoryNode | null;
  groupId?: string;
  groups: CategoryGroupNode[];
  onClose: () => void;
}) {
  const mutate = useCategoryMutation();
  const [name, setName] = useState(node?.name ?? "");
  const [group, setGroup] = useState(node?.group_id ?? groupId ?? "");
  const kind = groups.find((g) => g.id === group)?.kind ?? "expense";
  const [role, setRole] = useState(node?.role ?? DEFAULT_ROLE[kind]);
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);
  const nameError = name.trim() ? conflict : "Informe o nome.";
  const groupError = group ? null : "Escolha o grupo.";
  const renamed = node !== null && name.trim() !== node.name;
  const dirty =
    name !== (node?.name ?? "") ||
    group !== (node?.group_id ?? groupId ?? "") ||
    (node !== null && role !== node.role);

  function submit() {
    setTouched(true);
    if (!name.trim() || groupError) return;
    setFailed(false);
    setConflict(null);
    const body = { name: name.trim(), group_id: group, role };
    mutate.mutate(node ? { op: "update", id: node.id, body } : { op: "create", body }, {
      onSuccess: () => {
        toast(`${name.trim()} salvo.`);
        onClose();
      },
      onError: (err) => {
        const msg = errorText(err);
        if (msg) setConflict(msg);
        else setFailed(true);
      },
    });
  }

  return (
    <SideForm
      open
      title={node ? "Editar categoria" : "Nova categoria"}
      dirty={dirty}
      saving={mutate.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      <FormField id="cat-nome" label="Nome" error={touched ? nameError : null}>
        <Input
          id="cat-nome"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => setTouched(true)}
          aria-invalid={Boolean(touched && nameError)}
        />
      </FormField>
      {renamed && (
        <p className="rounded-md bg-warning-tint px-3 py-2 type-body-sm text-warning">
          Renomear reflete em todo o histórico: as {node?.transaction_count ?? 0} transações passam a
          mostrar o nome novo.
        </p>
      )}
      <FormField id="cat-grupo" label="Grupo" error={touched ? groupError : null}>
        <select
          id="cat-grupo"
          value={group}
          onChange={(e) => {
            setGroup(e.target.value);
            const k = groups.find((g) => g.id === e.target.value)?.kind ?? "expense";
            setRole(DEFAULT_ROLE[k]);
          }}
          className="h-9 w-full rounded-md border border-input bg-background px-3 type-body"
        >
          <option value="">Escolha…</option>
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name} ({KIND_LABEL[g.kind].toLowerCase()})
            </option>
          ))}
        </select>
      </FormField>
      <FormField id="cat-role" label="Papel nos termos de dinheiro">
        <select
          id="cat-role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="h-9 w-full rounded-md border border-input bg-background px-3 type-body"
        >
          {ROLES[kind].map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </FormField>
    </SideForm>
  );
}

function GroupForm({ node, onClose }: { node: CategoryGroupNode | null; onClose: () => void }) {
  const mutate = useCategoryMutation();
  const [name, setName] = useState(node?.name ?? "");
  const [kind, setKind] = useState<GroupKind>(node?.kind ?? "expense");
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);
  const locked = (node?.transaction_count ?? 0) > 0;
  const error = name.trim() ? conflict : "Informe o nome do grupo.";

  function submit() {
    setTouched(true);
    if (!name.trim()) return;
    setFailed(false);
    setConflict(null);
    const body = { name: name.trim(), ...(locked ? {} : { kind }) };
    mutate.mutate(node ? { op: "update-group", id: node.id, body } : { op: "create-group", body: { name: name.trim(), kind } }, {
      onSuccess: () => {
        toast(`${name.trim()} salvo.`);
        onClose();
      },
      onError: (err) => {
        const msg = errorText(err);
        if (msg) setConflict(msg);
        else setFailed(true);
      },
    });
  }

  return (
    <SideForm
      open
      title={node ? "Editar grupo" : "Novo grupo"}
      dirty={name !== (node?.name ?? "") || kind !== (node?.kind ?? "expense")}
      saving={mutate.isPending}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      <FormField id="grp-nome" label="Nome" error={touched ? error : null}>
        <Input id="grp-nome" value={name} onChange={(e) => setName(e.target.value)} onBlur={() => setTouched(true)} />
      </FormField>
      <FormField id="grp-tipo" label="Tipo de movimento">
        <select
          id="grp-tipo"
          value={kind}
          disabled={locked}
          onChange={(e) => setKind(e.target.value as GroupKind)}
          className="h-9 w-full rounded-md border border-input bg-background px-3 type-body disabled:opacity-60"
        >
          {(Object.keys(KIND_LABEL) as GroupKind[]).map((k) => (
            <option key={k} value={k}>
              {KIND_LABEL[k]}
            </option>
          ))}
        </select>
        {locked && (
          <p className="type-caption text-muted-foreground">
            O tipo de um grupo com transações não muda. Para trocar, mova as subcategorias.
          </p>
        )}
      </FormField>
    </SideForm>
  );
}

export default function CategoriasPage() {
  const [showArchived, setShowArchived] = useState(false);
  const tree = useCategoryTree(showArchived);
  const mutate = useCategoryMutation();
  const [editing, setEditingState] = useState<Editing>(null);
  // O painel abre por estado: guarda quem abriu e devolve o foco a ele ao fechar (UX-DR43).
  const opener = useRef<HTMLElement | null>(null);
  const setEditing = (next: Editing) => {
    if (next) opener.current = document.activeElement as HTMLElement | null;
    setEditingState(next);
    if (!next) requestAnimationFrame(() => opener.current?.focus());
  };
  const groups = tree.data ?? [];
  const activeGroups = groups.filter((g) => g.is_active);

  const act = (label: string, run: Parameters<typeof mutate.mutate>[0]) =>
    mutate.mutate(run, {
      onSuccess: () => toast(label),
      onError: (err) => toast(errorText(err) ?? "Não foi possível salvar. Nada foi perdido."),
    });

  if (tree.isError) return <p className="type-body text-negative">Não foi possível carregar as categorias.</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex items-center gap-2 type-body-sm">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
          Mostrar arquivadas
        </label>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setEditing({ type: "group", node: null })}>
            Novo grupo
          </Button>
          <Button variant="secondary" onClick={() => setEditing({ type: "category", node: null })}>
            <PlusIcon aria-hidden />
            Nova categoria
          </Button>
        </div>
      </div>

      {!tree.isLoading && groups.length === 0 && (
        <div className="rounded-lg border border-border bg-card shadow-card p-card-padding">
          <h2 className="type-section-title">Nenhuma categoria.</h2>
          <p className="type-body text-muted-foreground">Crie o primeiro grupo.</p>
          <Button className="mt-3" onClick={() => setEditing({ type: "group", node: null })}>
            Nova categoria
          </Button>
        </div>
      )}

      <ul className="space-y-section-gap">
        {groups.map((g) => (
          <li key={g.id} className="rounded-lg border border-border bg-card shadow-card">
            <div
              className={cn(
                "flex items-center justify-between gap-2 border-b border-border px-4 py-2",
                !g.is_active && "text-muted-foreground",
              )}
            >
              <div className="flex items-center gap-2">
                <h2 className="type-section-title">{g.name}</h2>
                <StatusBadge>{g.kind_label.toLowerCase()}</StatusBadge>
                {!g.is_active && <StatusBadge>arquivado</StatusBadge>}
              </div>
              <RowActions
                subject={`o grupo ${g.name}`}
                onEdit={() => setEditing({ type: "group", node: g })}
                extra={[
                  {
                    label: `Nova subcategoria em ${g.name}`,
                    icon: PlusIcon,
                    onClick: () => setEditing({ type: "category", node: null, groupId: g.id }),
                  },
                ]}
              />
            </div>
            {/* no celular o papel vai para baixo do nome e as ações ficam estreitas (v2.2): a
                largura fixa por % cortava os botões */}
            <table className="w-full type-body-sm">
              <caption className="sr-only">Subcategorias de {g.name}</caption>
              <thead className="sr-only">
                <tr>
                  <th scope="col">Subcategoria</th>
                  <th scope="col">Papel</th>
                  <th scope="col">Transações</th>
                  <th scope="col">Ações</th>
                </tr>
              </thead>
              <tbody>
                {g.categories.map((c) => (
                  <tr
                    key={c.id}
                    className={cn("border-t border-border first:border-t-0 hover:bg-row-highlight", !c.is_active && "text-muted-foreground")}
                  >
                    <td className="px-4 py-2 break-words">
                      {c.name} {!c.is_active && <StatusBadge>arquivada</StatusBadge>}
                      <span className="block type-caption text-muted-foreground sm:hidden">{c.role_label}</span>
                    </td>
                    <td className="hidden px-4 py-2 text-muted-foreground sm:table-cell">{c.role_label}</td>
                    <td className="w-px px-2 py-2 text-right type-num-table sm:px-4">{c.transaction_count}</td>
                    <td className="w-px px-2 py-1 text-right whitespace-nowrap">
                      <RowActions
                        subject={c.name}
                        onEdit={() => setEditing({ type: "category", node: c })}
                        onDelete={
                          c.transaction_count === 0
                            ? () => act(`${c.name} apagada.`, { op: "delete", id: c.id })
                            : undefined
                        }
                        extra={[
                          c.is_active
                            ? {
                                label: `Arquivar ${c.name}`,
                                icon: ArchiveIcon,
                                onClick: () => act(`${c.name} arquivada.`, { op: "update", id: c.id, body: { is_active: false } }),
                              }
                            : {
                                label: `Reativar ${c.name}`,
                                icon: ArchiveRestoreIcon,
                                onClick: () => act(`${c.name} reativada.`, { op: "update", id: c.id, body: { is_active: true } }),
                              },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </li>
        ))}
      </ul>

      {editing?.type === "category" && (
        <CategoryForm
          key={editing.node?.id ?? `nova-${editing.groupId ?? ""}`}
          node={editing.node}
          groupId={editing.groupId}
          groups={activeGroups}
          onClose={() => setEditing(null)}
        />
      )}
      {editing?.type === "group" && (
        <GroupForm key={editing.node?.id ?? "novo"} node={editing.node} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}
