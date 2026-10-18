"use client";

// Reabrir mês (Story 5.5 — FR-33, UX-DR40): congelado × recalculado só nas métricas que mudam (a
// prévia vem da API, com o arredondamento dela). Confirmar reabre; fechar de novo cria a versão
// seguinte e as anteriores ficam guardadas. Falha não muda nada e oferece tentar de novo.
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
import { useReopenMonth, useReopenPreview } from "@/lib/closing";
import { formatBRL, formatMonth, formatPercent } from "@/lib/format";
import type { ReopenRow } from "@/types/closing";

function show(row: ReopenRow, value: number | null): string {
  if (value === null) return "—";
  return row.metric === "taxa_poupanca" || row.metric === "rentabilidade"
    ? formatPercent(value)
    : formatBRL(value);
}

export function ReopenDialog({ periodo, onClose }: { periodo: string | null; onClose: () => void }) {
  const preview = useReopenPreview(periodo);
  const reopen = useReopenMonth();
  const [failed, setFailed] = useState(false);
  const retryRef = useRef<HTMLButtonElement>(null);
  const label = periodo ? formatMonth(periodo) : "";

  useEffect(() => {
    if (failed) retryRef.current?.focus();
  }, [failed]);

  function submit() {
    if (!periodo) return;
    setFailed(false);
    reopen.mutate(periodo, {
      onSuccess: () => {
        toast(`${label} reaberto.`);
        onClose();
      },
      onError: () => setFailed(true),
    });
  }

  const rows = preview.data?.rows ?? [];
  return (
    <AlertDialog open={periodo !== null} onOpenChange={(v) => (v ? undefined : onClose())}>
      <AlertDialogContent className="sm:max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>Reabrir {label}</AlertDialogTitle>
          <AlertDialogDescription>
            O mês volta a ser calculado ao vivo. Fechar de novo congela uma nova versão; a anterior
            fica guardada.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {preview.isLoading ? (
          <div className="h-24 animate-pulse rounded bg-muted" aria-hidden />
        ) : preview.isError ? (
          <p className="type-body-sm text-negative">Não foi possível calcular a prévia.</p>
        ) : rows.length === 0 ? (
          <p className="type-body-sm text-muted-foreground">
            Nada mudou desde o fechamento: os números recalculados são os congelados.
          </p>
        ) : (
          <table className="w-full type-body-sm">
            <thead>
              <tr className="text-muted-foreground">
                <th className="text-left font-normal">Métrica</th>
                <th className="text-right font-normal">Congelado</th>
                <th className="text-right font-normal">Recalculado</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.metric}>
                  <td>{r.label}</td>
                  <td className="text-right type-num-table">{show(r, r.frozen)}</td>
                  <td className="text-right type-num-table">{show(r, r.live)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {failed && (
          <div role="alert" className="flex flex-wrap items-center gap-2 type-body-sm text-negative">
            Não foi possível reabrir {label}. Nada foi perdido.
            <Button ref={retryRef} size="sm" variant="secondary" onClick={submit}>
              Tentar de novo
            </Button>
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel autoFocus>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            disabled={reopen.isPending || !preview.isSuccess}
            onClick={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            Reabrir {label}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
