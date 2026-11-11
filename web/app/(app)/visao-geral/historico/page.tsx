"use client";

// Visão geral › Histórico: com o Seletor de leitura, o período × o anterior × a média 12m (Story
// 9.1); abaixo, o card de Fechamento de mês (Story 5.4): os meses de jul/2024 até hoje com o Selo de
// estado (fechado / aberto / ajuste) e "Fechar {mês}" nos meses abertos que já terminaram, pelo
// Checklist de fechamento; "Reabrir {mês}" nos fechados (5.5). Desde a v2.2 os fechados antigos
// ficam agrupados por ano, recolhidos.
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { CloseDialog } from "@/components/closing/CloseDialog";
import { ReadingSelector, useLeitura } from "@/components/data/ReadingSelector";
import { ReopenDialog } from "@/components/closing/ReopenDialog";
import { Section } from "@/components/data/Section";
import { StatusBadge } from "@/components/data/StatusBadge";
import { HistoryCharts } from "@/components/overview/HistoryCharts";
import { HistoryComparison } from "@/components/overview/HistoryComparison";
import { Button } from "@/components/ui/button";
import { useMonthStates } from "@/lib/closing";
import { formatDate, formatMonth } from "@/lib/format";
import { currentMonthBRT } from "@/lib/period";
import { usePeriodo } from "@/lib/use-periodo";
import type { MonthState } from "@/types/closing";

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
  const { periodo } = usePeriodo();
  const leitura = useLeitura();

  if (months.isError) {
    return <p className="type-body text-negative">Não foi possível carregar os meses.</p>;
  }
  const rows = [...(months.data ?? [])].reverse();
  const lastClosed = rows.find((m) => m.status === "fechado");
  const recent = rows.filter((m) => m.status !== "fechado" || m === lastClosed);
  const years = Object.entries(
    rows
      .filter((m) => !recent.includes(m))
      .reduce<Record<string, MonthState[]>>((acc, m) => {
        (acc[m.month.slice(0, 4)] ??= []).push(m);
        return acc;
      }, {}),
  ).sort(([a], [b]) => b.localeCompare(a));
  return (
    <div className="space-y-section-gap">
      <div className="space-y-3">
        <ReadingSelector />
        <HistoryComparison periodo={periodo} leitura={leitura} />
        <HistoryCharts periodo={periodo} leitura={leitura} />
      </div>
      <section aria-labelledby="fechamento-mes" className="space-y-3">
        <h2 id="fechamento-mes" className="type-section-title">
          Fechamento de mês
        </h2>
        {months.isLoading && <div className="h-24 animate-pulse rounded-lg bg-muted" aria-hidden />}
        {/* À vista só o que pede ação (aberto, ajuste) e o último fechado; os fechados ficam por
            ano, recolhidos (v2.2). */}
        {recent.length > 0 && (
          <ul className="divide-y divide-border rounded-lg border border-border bg-card shadow-card">
            {recent.map((m) => (
              <MonthRow key={m.month} m={m} current={current} onClose={setClosing} onReopen={setPicked} />
            ))}
          </ul>
        )}
        {years.map(([year, list]) => (
          <Section
            key={year}
            title={year}
            summary={`${list.length} fechado${list.length > 1 ? "s" : ""}`}
            className="overflow-hidden"
          >
            <ul className="-mx-card-padding -mb-card-padding divide-y divide-border border-t border-border">
              {list.map((m) => (
                <MonthRow key={m.month} m={m} current={current} onClose={setClosing} onReopen={setPicked} />
              ))}
            </ul>
          </Section>
        ))}
      </section>
      <CloseDialog periodo={closing} onClose={() => setClosing(null)} />
      <ReopenDialog periodo={reopening} onClose={closeReopen} />
    </div>
  );
}

function MonthRow({
  m,
  current,
  onClose,
  onReopen,
}: {
  m: MonthState;
  current: string;
  onClose: (mes: string) => void;
  onReopen: (mes: string) => void;
}) {
  const mes = m.month.slice(0, 7);
  return (
    <li className="flex min-h-12 items-center justify-between gap-2 px-4 py-2 type-body-sm">
      <span className="flex items-center gap-2">
        <span className="type-num-body w-20">{formatMonth(mes)}</span>
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
      {m.status === "aberto" && mes < current && (
        <Button size="sm" variant="secondary" onClick={() => onClose(mes)}>
          Fechar {formatMonth(mes)}
        </Button>
      )}
      {m.status !== "aberto" && (
        <Button size="sm" variant="ghost" onClick={() => onReopen(mes)}>
          Reabrir {formatMonth(mes)}
        </Button>
      )}
    </li>
  );
}
