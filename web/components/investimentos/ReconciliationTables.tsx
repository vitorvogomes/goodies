"use client";

// Conciliação com o consolidado B3 e com as carteiras (Story 7.9 — FR-26, AD-13): por ativo, a
// quantidade no app × a da origem, a diferença e o Selo (conferido | divergente | valor calculado),
// com o Carimbo da origem. Tolerâncias são da API (exata em ações/FII/ETF, 0,01 título no Tesouro,
// cripto sem tolerância); o front só exibe.
import Link from "next/link";
import { usePathname } from "next/navigation";

import { DateStamp } from "@/components/data/DateStamp";
import { StatusBadge } from "@/components/data/StatusBadge";
import { fmtQty, fmtWhen } from "@/lib/format";
import { reconciliationSummary, useReconciliation } from "@/lib/positions";
import type { ReconRow } from "@/types/positions";

function qty(v: string | null): string {
  return v === null ? "—" : fmtQty(Number(v));
}

function Badge({ status }: { status: ReconRow["status"] }) {
  if (status === "divergente") return <StatusBadge tone="divergence">divergente</StatusBadge>;
  return <StatusBadge>{status}</StatusBadge>;
}

function Table({ label, origin, rows }: { label: string; origin: string; rows: ReconRow[] }) {
  return (
    <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card" tabIndex={0} role="region" aria-label={label}>
      <table className="w-full type-body-sm">
        <caption className="sr-only">{label}</caption>
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2 text-left font-medium">Ativo</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">No app</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">{origin}</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Diferença</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Estado</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol} className="border-t border-border">
              <th scope="row" className="px-4 py-2 text-left font-normal">{r.symbol}</th>
              <td className="px-4 py-2 text-right type-num-table">{qty(r.app)}</td>
              <td className="px-4 py-2 text-right type-num-table">{qty(r.origin)}</td>
              <td className="px-4 py-2 text-right type-num-table">{qty(r.diff)}</td>
              <td className="px-4 py-2 text-right">
                <Badge status={r.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ReconciliationTables() {
  const pathname = usePathname();
  const recon = useReconciliation();
  if (recon.isError) return <p className="type-body text-negative">Não foi possível carregar a conciliação.</p>;
  if (!recon.data) return <div className="h-48 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />;
  const { b3, wallets } = recon.data;
  const summary = reconciliationSummary(recon.data);
  return (
    <div className="space-y-card-gap">
      {summary && (
        <p role="status" className="type-body">
          {summary}
        </p>
      )}
      <section aria-labelledby="concilia-b3" className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="concilia-b3" className="type-section-title">Consolidado B3</h2>
          <DateStamp asOf={b3.ref_date} source="consolidado B3" />
        </div>
        {b3.ref_date ? (
          <Table label="App × consolidado B3" origin="Consolidado B3" rows={b3.rows} />
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card shadow-card p-card-padding">
            <p className="type-body text-muted-foreground">
              Sem consolidado B3. Importe o consolidado (.xlsx) para conciliar.
            </p>
            <Link href={`${pathname}?importar=1`} className="type-body-sm font-medium text-primary underline-offset-4 hover:underline">
              Importar
            </Link>
          </div>
        )}
      </section>
      <section aria-labelledby="concilia-carteiras" className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="concilia-carteiras" className="type-section-title">Carteiras</h2>
          {wallets.stale ? (
            <StatusBadge tone="warning">sem scan desde {fmtWhen(wallets.attempt_at)}</StatusBadge>
          ) : (
            <span className="type-caption text-muted-foreground">scan de {fmtWhen(wallets.scanned_at)}</span>
          )}
        </div>
        {wallets.rows.length ? (
          <Table label="App × carteiras" origin="Carteira" rows={wallets.rows} />
        ) : (
          <p className="type-body text-muted-foreground">Nenhuma carteira escaneada.</p>
        )}
      </section>
    </div>
  );
}
