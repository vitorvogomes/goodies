"use client";

// STORY-02-16 — tela de rebalanceamento: input de aporte → sugestão por categoria.
import { useState } from "react";

import { Button, Card, Field, Input } from "@/components/ui";
import { formatBRL, formatPP } from "@/lib/format";
import { useRebalancing } from "@/lib/portfolio";

export default function RebalancingPage() {
  const [draft, setDraft] = useState("4500");
  const [amount, setAmount] = useState(4500);

  const { data, isLoading, isError } = useRebalancing(amount);

  function apply() {
    const value = Number(draft.replace(",", "."));
    if (Number.isFinite(value) && value >= 0) setAmount(value);
  }

  const suggestions = data ? Object.entries(data.suggestions) : [];

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-2xl font-semibold text-foreground">Rebalanceamento</h1>

      <Card>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <Field label="Quanto você quer aportar (R$)" htmlFor="amount">
              <Input
                id="amount"
                inputMode="decimal"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && apply()}
              />
            </Field>
          </div>
          <Button onClick={apply}>Calcular</Button>
        </div>
        <p className="mt-2 text-xs text-foreground/40">
          Nunca sugere venda — só aporta nas categorias abaixo da meta.
        </p>
      </Card>

      {isLoading && <p className="text-foreground/50">Calculando…</p>}
      {isError && <p className="text-loss">Erro ao calcular rebalanceamento.</p>}

      {data && data.message && (
        <Card>
          <p className="text-sm text-foreground/70">{data.message}</p>
        </Card>
      )}

      {data && suggestions.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-foreground/60">
              <tr>
                <th className="px-4 py-2.5 font-medium">Categoria</th>
                <th className="px-4 py-2.5 text-right font-medium">Desvio atual</th>
                <th className="px-4 py-2.5 text-right font-medium">Aporte sugerido</th>
              </tr>
            </thead>
            <tbody>
              {suggestions
                .sort((a, b) => b[1] - a[1])
                .map(([cat, value]) => (
                  <tr key={cat} className="border-t border-border">
                    <td className="px-4 py-2.5 text-foreground/80">{cat}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {data.deviations_pp[cat] != null ? (
                        <span
                          className={
                            data.deviations_pp[cat] >= 0 ? "text-gain" : "text-loss"
                          }
                        >
                          {formatPP(data.deviations_pp[cat])}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right font-medium tabular-nums text-accent">
                      {formatBRL(value)}
                    </td>
                  </tr>
                ))}
              <tr className="border-t border-border bg-muted/30">
                <td className="px-4 py-2.5 font-medium text-foreground/70">Total</td>
                <td />
                <td className="px-4 py-2.5 text-right font-semibold tabular-nums text-foreground/90">
                  {formatBRL(suggestions.reduce((s, [, v]) => s + v, 0))}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
