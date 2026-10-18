"use client";

// Checklist de fechamento (Story 5.4 — UX-DR40, DESIGN › closing-checklist): saldo PF conferido,
// transações revisadas e as pendências do mês — check neutro quando ok, ponto de aviso + link na
// pendência — e, abaixo, o resumo a congelar. Pendência que bloqueia desabilita o botão com o
// motivo; as outras viram "Fechar {mês} com {n} pendências" (o "fechar mesmo assim" fica gravado).
import { CheckIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

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
import { useChecklist, useCloseMonth } from "@/lib/closing";
import { formatBRL, formatMonth, formatPercent, formatSignedBRL } from "@/lib/format";
import type { ChecklistItem } from "@/types/closing";

function linkFor(item: ChecklistItem, periodo: string): string | null {
  switch (item.key) {
    case "saldo_pf":
      return `/caixa/transacoes?periodo=${periodo}`;
    case "revisadas":
      return `/caixa/transacoes?periodo=${periodo}&revisar=todas`;
    case "consolidado_ausente":
    case "mei_nao_cobre":
      return `/visao-geral/historico?importar=1`;
    case "sem_scan_cripto":
      return "/refresh";
    default:
      return null;
  }
}

export function CloseDialog({ periodo, onClose }: { periodo: string | null; onClose: () => void }) {
  const checklist = useChecklist(periodo);
  const close = useCloseMonth();
  const [failed, setFailed] = useState(false);
  const retryRef = useRef<HTMLButtonElement>(null);
  const label = periodo ? formatMonth(periodo) : "";

  useEffect(() => {
    if (failed) retryRef.current?.focus();
  }, [failed]);

  const data = checklist.data;
  const confirmable = (data?.items ?? []).filter((i) => !i.ok && i.kind === "confirma");
  const blocking = (data?.items ?? []).filter((i) => !i.ok && i.kind === "bloqueia");

  function submit() {
    if (!periodo) return;
    setFailed(false);
    close.mutate(
      { periodo, confirmar: confirmable.map((i) => i.code ?? i.key) },
      {
        onSuccess: () => {
          toast(`${label} fechado.`);
          onClose();
        },
        onError: () => setFailed(true),
      },
    );
  }

  const s = data?.summary;
  return (
    <AlertDialog open={periodo !== null} onOpenChange={(v) => (v ? undefined : onClose())}>
      <AlertDialogContent className="sm:max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>Fechar {label}</AlertDialogTitle>
          <AlertDialogDescription>
            O resumo abaixo fica congelado. Dado novo do mês depois disso vira ajuste.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {!data ? (
          <div className="h-32 animate-pulse rounded bg-muted" aria-hidden />
        ) : (
          <>
            <ul className="space-y-1.5 type-body-sm">
              {data.items.map((item) => {
                const href = !item.ok && periodo ? linkFor(item, periodo) : null;
                return (
                  <li key={item.key} className="flex items-start gap-2">
                    {item.ok ? (
                      <CheckIcon aria-label="ok" className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <span
                        aria-label={item.kind === "bloqueia" ? "bloqueia" : "pendência"}
                        className={
                          item.kind === "bloqueia"
                            ? "mt-1.5 size-2 shrink-0 rounded-full bg-negative ring-4 ring-negative-tint"
                            : "mt-1.5 size-2 shrink-0 rounded-full bg-warning-dot ring-4 ring-warning-tint"
                        }
                      />
                    )}
                    <span>
                      {item.message}{" "}
                      {href && (
                        <Link href={href} className="text-positive underline" onClick={onClose}>
                          Ver
                        </Link>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
            {s && (
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 rounded-md bg-muted px-3 py-2 type-body-sm">
                <dt className="text-muted-foreground">Resultado do mês</dt>
                <dd className="text-right type-num-table">{formatSignedBRL(s.resultado_mes)}</dd>
                <dt className="text-muted-foreground">Receitas</dt>
                <dd className="text-right type-num-table">{formatBRL(s.receitas)}</dd>
                <dt className="text-muted-foreground">Gastos</dt>
                <dd className="text-right type-num-table">{formatBRL(s.gastos)}</dd>
                <dt className="text-muted-foreground">Taxa de poupança</dt>
                <dd className="text-right type-num-table">
                  {s.taxa_poupanca === null ? "—" : formatPercent(s.taxa_poupanca)}
                </dd>
                <dt className="text-muted-foreground">Patrimônio</dt>
                <dd className="text-right type-num-table">{formatBRL(s.patrimonio)}</dd>
              </dl>
            )}
            {blocking.length > 0 && (
              <p className="type-body-sm text-negative">Não dá para fechar: {blocking[0].message}</p>
            )}
          </>
        )}
        {failed && (
          <div role="alert" className="flex flex-wrap items-center gap-2 type-body-sm text-negative">
            Não foi possível fechar {label}. Nada foi perdido.
            <Button ref={retryRef} size="sm" variant="secondary" onClick={submit}>
              Tentar de novo
            </Button>
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel autoFocus>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            disabled={!data || blocking.length > 0 || close.isPending}
            onClick={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            {confirmable.length > 0
              ? `Fechar ${label} com ${confirmable.length} ${confirmable.length === 1 ? "pendência" : "pendências"}`
              : `Fechar ${label}`}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
