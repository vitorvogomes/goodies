"use client";

// Histórico de imports no rodapé do Hub (Story 3.14 — FR-6, UX-DR21/29): lotes do mais recente para
// o mais antigo, com data, arquivos e contagem. Só o último lote aplicado com até 7 dias tem
// Desfazer; o Diálogo mostra o efeito em números (foco em Cancelar) e uma falha não remove nada.
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/data/StatusBadge";
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
import { formatDate } from "@/lib/format";
import { useImportHistory, useUndoBatch, useUndoPreview } from "@/lib/ingest";
import type { UndoPreview } from "@/types/ingest";

const UNDO_FAILED = "Não foi possível desfazer o lote. Nada foi perdido.";

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

export function undoSummary(p: UndoPreview): string {
  const parts = [
    plural(p.transactions, "transação", "transações"),
    plural(p.operations, "operação", "operações"),
    plural(p.categorizations, "categorização", "categorizações"),
    plural(p.rules, "regra", "regras"),
  ];
  const extra = [
    p.balances ? plural(p.balances, "saldo informado", "saldos informados") : null,
    p.snapshots ? plural(p.snapshots, "posição do consolidado", "posições do consolidado") : null,
  ].filter(Boolean);
  const prices = p.prices
    ? ` ${plural(p.prices, "preço volta", "preços voltam")} ao do consolidado anterior.`
    : "";
  const all = [...parts, ...extra];
  const list = `${all.slice(0, -1).join(", ")} e ${all[all.length - 1]}`;
  return `Remove ${list} do lote de ${formatDate(p.applied_at.slice(0, 10))}.${prices}`;
}

export function ImportHistory() {
  const history = useImportHistory();
  const [target, setTarget] = useState<string | null>(null);
  const preview = useUndoPreview(target);
  const undo = useUndoBatch();
  const [failed, setFailed] = useState(false);
  const retryRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (failed) retryRef.current?.focus();
  }, [failed]);

  const run = () => {
    if (!target) return;
    setFailed(false);
    undo.mutate(target, {
      onSuccess: () => {
        toast("Lote desfeito.");
        setTarget(null);
      },
      onError: () => setFailed(true),
    });
  };

  const items = history.data?.items ?? [];
  return (
    <section aria-labelledby="historico" className="space-y-2">
      <h3 id="historico" className="type-label text-muted-foreground">
        Histórico de imports
      </h3>
      {history.data?.undo_note && (
        <p className="type-body-sm text-muted-foreground">{history.data.undo_note}</p>
      )}
      <ul className="divide-y divide-border rounded-lg border border-border">
        {items.length === 0 && !history.isLoading && (
          <li className="px-3 py-2 type-body-sm text-muted-foreground">Nenhum import ainda.</li>
        )}
        {items.slice(0, 10).map((b) => (
          <li key={b.id} className="flex items-start justify-between gap-2 px-3 py-2 type-body-sm">
            <div className="min-w-0">
              <span className="font-semibold">
                {formatDate((b.applied_at ?? b.created_at).slice(0, 10))}
              </span>{" "}
              {b.status === "undone" && <StatusBadge>desfeito</StatusBadge>}
              {b.status === "legacy" && <StatusBadge>legado</StatusBadge>}
              <span className="block truncate text-muted-foreground">
                {b.files.map((f) => f.file_name ?? f.source).join(", ") || "—"}
                {b.new !== null && ` · ${plural(b.new, "novo", "novos")}`}
              </span>
            </div>
            {b.undoable && (
              <Button size="sm" variant="secondary" onClick={() => setTarget(b.id)}>
                Desfazer
              </Button>
            )}
          </li>
        ))}
      </ul>
      <AlertDialog
        open={target !== null}
        onOpenChange={(v) => {
          if (!v) {
            setTarget(null);
            setFailed(false);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Desfazer o último lote</AlertDialogTitle>
            <AlertDialogDescription>
              {preview.data ? undoSummary(preview.data) : "Calculando o que sai…"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {failed && (
            <div role="alert" className="flex flex-wrap items-center gap-2 type-body-sm text-negative">
              {UNDO_FAILED}
              <Button ref={retryRef} size="sm" variant="secondary" onClick={run}>
                Tentar de novo
              </Button>
            </div>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel autoFocus>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={!preview.data || undo.isPending}
              onClick={(e) => {
                e.preventDefault();
                run();
              }}
            >
              Desfazer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
