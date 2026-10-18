"use client";

// Faixa de avisos do Painel (Story 4.2 — FR-14, UX-DR13): até 3 Linhas de aviso (divergências
// primeiro, a ordem da API) e "Ver todos ({n})", com {n} igual ao Sino. Sem avisos: "Nenhum aviso.
// Dados até {dd/mm/aaaa}."
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { AlertRow } from "@/components/alerts/AlertRow";
import { useAlertCenter } from "@/lib/alerts";
import { formatDate } from "@/lib/format";

export function AlertsStrip() {
  const alerts = useAlertCenter();
  const pathname = usePathname();
  const params = useSearchParams();
  if (alerts.isError) {
    return (
      <p className="type-body-sm text-negative">
        Não foi possível carregar os avisos.{" "}
        <button type="button" className="underline" onClick={() => alerts.refetch()}>
          Tentar de novo
        </button>
      </p>
    );
  }
  if (!alerts.data) return <div className="h-12 animate-pulse rounded-lg bg-muted" aria-hidden />;
  const { items, total, data_until } = alerts.data;
  if (total === 0) {
    return (
      <p className="rounded-lg border border-border bg-card px-4 py-3 type-body-sm text-muted-foreground">
        Nenhum aviso.{data_until ? ` Dados até ${formatDate(data_until)}.` : ""}
      </p>
    );
  }
  const all = new URLSearchParams(params);
  all.set("avisos", "1");
  return (
    <section aria-label="Avisos" className="rounded-lg border border-border bg-card">
      <ul className="divide-y divide-border">
        {items.slice(0, 3).map((a) => (
          <li key={a.key}>
            <AlertRow alert={a} />
          </li>
        ))}
      </ul>
      <div className="border-t border-border px-4 py-2 text-right type-body-sm">
        <Link href={`${pathname}?${all}`} className="text-positive underline">
          Ver todos ({total})
        </Link>
      </div>
    </section>
  );
}
