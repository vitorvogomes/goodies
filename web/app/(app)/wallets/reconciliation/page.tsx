"use client";

// STORY-04-11 — Reconciliação: saldo escaneado (wallet_positions) vs registrado
// (net das asset_operations). Delta != 0 = divergência a investigar.
import { Button } from "@/components/ui";
import { fmtQty } from "@/lib/format";
import { useReconciliation } from "@/lib/wallet";

// alinhado ao display: fmtQty mostra 8 casas → o que arredonda p/ 0 (|Δ|<5e-9) não conta
// nem colore como divergência (senão um delta-poeira aparecia como "+0" colorido).
const EPS = 5e-9;

function deltaClass(delta: number): string {
  if (Math.abs(delta) < EPS) return "text-foreground/40";
  return delta > 0 ? "text-gain" : "text-loss";
}

function fmtDelta(delta: number): string {
  if (Math.abs(delta) < EPS) return "0";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${fmtQty(delta)}`;
}

export default function ReconciliationPage() {
  const { data, isLoading, isError } = useReconciliation();
  const rows = data ?? [];
  const diverged = rows.filter((r) => Math.abs(r.delta) >= EPS).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-mono text-2xl font-semibold text-foreground">Reconciliação</h1>
        <a href="/wallets">
          <Button variant="ghost">Carteiras Cripto</Button>
        </a>
      </div>

      <p className="text-xs text-foreground/50">
        Compara a quantidade <strong>escaneada</strong> (carteiras) com a quantidade{" "}
        <strong>registrada</strong> (net das operações). Delta ≠ 0 indica divergência —
        operação não lançada, taxa/rendimento, ou ativo só em carteira.
      </p>

      {rows.length > 0 && (
        <div className="text-xs text-foreground/50">
          Divergências{" "}
          <span className={`tabular-nums ${diverged > 0 ? "text-warning" : "text-foreground/70"}`}>
            {diverged}
          </span>{" "}
          de {rows.length}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-foreground/60">
            <tr>
              <th className="px-4 py-2.5 font-medium">Ativo</th>
              <th className="px-4 py-2.5 text-right font-medium">Escaneado</th>
              <th className="px-4 py-2.5 text-right font-medium">Registrado</th>
              <th className="px-4 py-2.5 text-right font-medium">Delta</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-foreground/50">
                  Carregando…
                </td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-loss">
                  Erro ao carregar a reconciliação.
                </td>
              </tr>
            )}
            {!isLoading && !isError && rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-foreground/50">
                  Nada para reconciliar ainda.
                </td>
              </tr>
            )}
            {!isLoading &&
              !isError &&
              rows.map((r) => (
                <tr key={r.asset_symbol} className="border-t border-border">
                  <td className="px-4 py-2.5 font-medium text-foreground/90">{r.asset_symbol}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                    {fmtQty(r.scanned_quantity)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                    {fmtQty(r.registered_quantity)}
                  </td>
                  <td
                    className={`px-4 py-2.5 text-right font-medium tabular-nums ${deltaClass(r.delta)}`}
                  >
                    {fmtDelta(r.delta)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
