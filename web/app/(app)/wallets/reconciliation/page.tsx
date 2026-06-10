"use client";

// STORY-04-11 — Reconciliação: saldo escaneado (wallet_positions) vs registrado
// (net das asset_operations). Delta != 0 = divergência a investigar.
import { Money } from "@/components/Money";
import { Button } from "@/components/ui";
import { fmtQty, formatBRL, formatRate } from "@/lib/format";
import { useCryptoSleeve } from "@/lib/portfolio";
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

function ValuePanel() {
  const { data: s } = useCryptoSleeve();
  if (!s) return null;
  const tone = s.resultado < 0 ? "text-loss" : "text-gain";
  return (
    <div className="rounded-2xl border border-border bg-muted/20 p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wide text-foreground/60">
        Reconciliação de valor — cripto (sleeve)
      </div>
      <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <div>
          <div className="text-xs text-foreground/50">Investido (líq.)</div>
          <div className="tabular-nums text-foreground/80">{formatBRL(s.net_invested_brl)}</div>
        </div>
        <div>
          <div className="text-xs text-foreground/50">Valor atual</div>
          <Money brl={s.current_value_brl} usd={s.current_value_usd} usdPartial={s.usd_partial} />
        </div>
        <div>
          <div className="text-xs text-foreground/50">Resultado</div>
          <div className={`tabular-nums ${tone}`}>{formatBRL(s.resultado)}</div>
        </div>
        <div>
          <div className="text-xs text-foreground/50">XIRR</div>
          <div className={`tabular-nums ${tone}`}>{formatRate(s.xirr)}</div>
        </div>
      </div>
      {s.by_rail.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {s.by_rail.map((r) => (
            <span
              key={r.rail}
              className="rounded bg-muted/60 px-2 py-0.5 text-xs text-foreground/60"
            >
              {r.rail} <span className="tabular-nums">{formatBRL(r.current_value_brl)}</span>
            </span>
          ))}
        </div>
      )}
      {s.stale_value && (
        <p className="mt-2 text-xs text-warning">
          ⚠ algum ativo sem preço — valor atual parcial.
        </p>
      )}
    </div>
  );
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

      <ValuePanel />

      <p className="text-xs text-foreground/50">
        Acima, a reconciliação de <strong>valor</strong> (investido via Nubank vs valor atual
        das carteiras → resultado). Abaixo, a de <strong>quantidade</strong>: o saldo{" "}
        <strong>escaneado</strong> vs o <strong>registrado</strong> (net das operações). Delta
        ≠ 0 indica divergência — operação não lançada, taxa/rendimento, ou ativo só em carteira.
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
              <th className="px-4 py-2.5 text-right font-medium">Valor</th>
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
                  <td className="px-4 py-2.5 text-right">
                    <Money brl={r.value_brl} usd={r.value_usd} />
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
