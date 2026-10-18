"use client";

// Visão geral › Histórico (Story 5.4, mínimo; a comparação entre meses chega na 9.1): os meses de
// jul/2024 até hoje com o Selo de estado (fechado / aberto / ajuste) e "Fechar {mês}" nos meses
// abertos que já terminaram, pelo Checklist de fechamento; "Reabrir {mês}" nos fechados (5.5).
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { CloseDialog } from "@/components/closing/CloseDialog";
import { ReopenDialog } from "@/components/closing/ReopenDialog";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/button";
import { useMonthStates } from "@/lib/closing";
import { formatDate, formatMonth } from "@/lib/format";
import { currentMonthBRT } from "@/lib/period";

export default function HistoricoPage() {
  const months = useMonthStates();
  const [closing, setClosing] = useState<string | null>(null);
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  // o aviso "Ajuste em {mês}" abre o diálogo pelo ?reabrir=AAAA-MM (Story 5.6); fechar o diálogo
  // tira o parâmetro, para voltar/recarregar não reabrir o diálogo de um mês já aberto
  const [picked, setPicked] = useState<string | null>(null);
  const reopening = picked ?? params.get("reabrir");
  function closeReopen() {
    setPicked(null);
    if (params.has("reabrir")) {
      const next = new URLSearchParams(params);
      next.delete("reabrir");
      router.replace(next.size ? `${pathname}?${next}` : pathname);
    }
  }
  const current = currentMonthBRT();

  if (months.isError) {
    return <p className="type-body text-negative">Não foi possível carregar os meses.</p>;
  }
  const rows = [...(months.data ?? [])].reverse();
  return (
    <div className="space-y-3">
      <ul className="divide-y divide-border rounded-lg border border-border bg-card">
        {months.isLoading && <li className="h-24 animate-pulse bg-muted" aria-hidden />}
        {rows.map((m) => {
          const periodo = m.month.slice(0, 7);
          return (
            <li key={m.month} className="flex items-center justify-between gap-2 px-4 py-2 type-body-sm">
              <span className="flex items-center gap-2">
                <span className="type-num-body w-20">{formatMonth(periodo)}</span>
                <StatusBadge
                  tone={m.status === "ajuste" ? "warning" : "neutral"}
                  tooltip={
                    m.status === "fechado" && m.closed_at
                      ? `Fechado em ${formatDate(m.closed_at.slice(0, 10))}${m.origin === "retro" ? " (retroativo)" : ""}.`
                      : m.status === "ajuste"
                        ? "Dado novo depois do fechamento: o resumo congelado não mudou."
                        : undefined
                  }
                >
                  {m.status}
                </StatusBadge>
              </span>
              {m.status === "aberto" && periodo < current && (
                <Button size="sm" variant="secondary" onClick={() => setClosing(periodo)}>
                  Fechar {formatMonth(periodo)}
                </Button>
              )}
              {m.status !== "aberto" && (
                <Button size="sm" variant="ghost" onClick={() => setPicked(periodo)}>
                  Reabrir {formatMonth(periodo)}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
      <CloseDialog periodo={closing} onClose={() => setClosing(null)} />
      <ReopenDialog periodo={reopening} onClose={closeReopen} />
    </div>
  );
}
