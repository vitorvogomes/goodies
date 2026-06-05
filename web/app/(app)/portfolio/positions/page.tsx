"use client";

// STORY-02-13 — tabela de posições com valor atual (preço manual em m2).
import { useState } from "react";

import { Button, Input } from "@/components/ui";
import { formatBRL, formatPercent } from "@/lib/format";
import { usePositions, useSetManualPrice } from "@/lib/portfolio";
import type { Position } from "@/types/portfolio";

function PriceCell({ pos }: { pos: Position }) {
  const setPrice = useSetManualPrice();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(pos.preco_atual ?? ""));

  function commit() {
    setEditing(false);
    const value = Number(draft.replace(",", "."));
    if (Number.isFinite(value) && value !== pos.preco_atual) {
      setPrice.mutate({ symbol: pos.asset_symbol, price: value });
    }
  }

  if (editing) {
    return (
      <Input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") setEditing(false);
        }}
        className="w-24 px-1.5 py-1 text-right"
      />
    );
  }
  return (
    <button
      type="button"
      onClick={() => {
        setDraft(String(pos.preco_atual ?? ""));
        setEditing(true);
      }}
      className="cursor-text tabular-nums hover:text-foreground"
    >
      {pos.preco_atual != null ? formatBRL(pos.preco_atual) : "definir"}
    </button>
  );
}

function ResultCell({ pos }: { pos: Position }) {
  if (pos.resultado == null || pos.resultado_pct == null) {
    return <span className="text-foreground/40">—</span>;
  }
  const tone = pos.resultado >= 0 ? "text-gain" : "text-loss";
  return (
    <span className={`tabular-nums ${tone}`}>
      {formatBRL(pos.resultado)}{" "}
      <span className="text-xs">({formatPercent(pos.resultado_pct)})</span>
    </span>
  );
}

export default function PositionsPage() {
  const { data, isLoading, isError } = usePositions();

  const totalAtual = (data ?? []).reduce((s, p) => s + (p.valor_atual ?? 0), 0);
  const totalCusto = (data ?? []).reduce((s, p) => s + p.custo_total, 0);
  const totalResult = totalAtual - totalCusto;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-mono text-2xl font-semibold text-foreground">Posições</h1>
        <a href="/portfolio">
          <Button variant="ghost">Visão geral</Button>
        </a>
      </div>

      {data && data.length > 0 && (
        <div className="flex flex-wrap justify-end gap-x-5 gap-y-1 text-xs text-foreground/50">
          <span>
            Custo <span className="tabular-nums text-foreground/70">{formatBRL(totalCusto)}</span>
          </span>
          <span>
            Atual <span className="tabular-nums text-foreground/70">{formatBRL(totalAtual)}</span>
          </span>
          <span>
            Resultado{" "}
            <span className={`tabular-nums ${totalResult < 0 ? "text-loss" : "text-gain"}`}>
              {formatBRL(totalResult)}
            </span>
          </span>
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-foreground/60">
            <tr>
              <th className="px-4 py-2.5 font-medium">Ativo</th>
              <th className="px-4 py-2.5 font-medium">Categoria</th>
              <th className="px-4 py-2.5 text-right font-medium">Qtd.</th>
              <th className="px-4 py-2.5 text-right font-medium">Preço médio</th>
              <th className="px-4 py-2.5 text-right font-medium">Preço atual</th>
              <th className="px-4 py-2.5 text-right font-medium">Valor atual</th>
              <th className="px-4 py-2.5 text-right font-medium">Resultado</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-foreground/50">
                  Carregando…
                </td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-loss">
                  Erro ao carregar posições.
                </td>
              </tr>
            )}
            {!isLoading && !isError && (data?.length ?? 0) === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-foreground/50">
                  Nenhuma posição aberta.
                </td>
              </tr>
            )}
            {(data ?? []).map((pos) => (
              <tr key={pos.asset_symbol} className="border-t border-border">
                <td className="px-4 py-2.5 font-medium text-foreground/90">
                  {pos.asset_symbol}
                  {pos.stale && (
                    <span className="ml-2 rounded bg-warning/15 px-1.5 py-0.5 text-xs text-warning">
                      sem preço
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-foreground/60">{pos.asset_category}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                  {pos.quantidade_net}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                  {formatBRL(pos.preco_medio)}
                </td>
                <td className="px-4 py-2.5 text-right text-foreground/80">
                  <PriceCell pos={pos} />
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                  {pos.valor_atual != null ? formatBRL(pos.valor_atual) : "—"}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <ResultCell pos={pos} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-foreground/40">
        Em m2 o preço atual é manual — clique em “definir” para informar a cotação.
        Preços automáticos chegam no m3 (Market Engine).
      </p>
    </div>
  );
}
