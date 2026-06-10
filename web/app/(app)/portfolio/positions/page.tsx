"use client";

// STORY-02-13 — tabela de posições com valor atual (preço manual em m2).
import { Fragment, useMemo, useState } from "react";

import { Money } from "@/components/Money";
import { Button, Input } from "@/components/ui";
import { formatBRL, formatPercent, formatRate, parseDecimalInput } from "@/lib/format";
import {
  useCryptoSleeve,
  useIncome,
  usePositions,
  useRevertPrice,
  useSetManualPrice,
} from "@/lib/portfolio";
import type { Position } from "@/types/portfolio";

// Input inline reutilizável (Enter salva, Esc/blur cancela ou salva). Parser pt-BR
// (parseDecimalInput) — "1.234,56" e "1234.56" ambos válidos.
function InlineNumber({
  initial,
  onCommit,
  onCancel,
}: {
  initial: string;
  onCommit: (raw: string) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  return (
    <Input
      autoFocus
      inputMode="decimal"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => onCommit(draft)}
      onKeyDown={(e) => {
        if (e.key === "Enter") onCommit(draft);
        if (e.key === "Escape") onCancel();
      }}
      className="w-24 px-1.5 py-1 text-right"
    />
  );
}

// Preço atual editável. Mesmo um preço automático (is_manual=false) pode ser sobrescrito —
// ao salvar, vira manual; o cadeado é só um indicador. Quando manual, oferece "↺ voltar ao
// automático" (libera o worker a cotar de novo).
function PriceCell({ pos }: { pos: Position }) {
  const setPrice = useSetManualPrice();
  const revert = useRevertPrice();
  const [editing, setEditing] = useState(false);

  function commit(raw: string) {
    setEditing(false);
    const t = raw.trim();
    if (t === "") return; // campo vazio: não sobrescreve
    const value = parseDecimalInput(t);
    if (Number.isFinite(value) && value >= 0 && value !== pos.preco_atual) {
      setPrice.mutate({ symbol: pos.asset_symbol, price: value });
    }
  }

  if (editing) {
    return (
      <InlineNumber
        initial={pos.preco_atual != null ? String(pos.preco_atual).replace(".", ",") : ""}
        onCommit={commit}
        onCancel={() => setEditing(false)}
      />
    );
  }

  const auto = !pos.is_manual && pos.preco_atual != null;
  return (
    <span className="inline-flex items-center gap-1.5">
      <button
        type="button"
        title={auto ? "Automático via API — clique para sobrescrever (vira manual)" : "Clique para definir o preço manual"}
        onClick={() => setEditing(true)}
        className="cursor-text border-b border-dashed border-foreground/30 tabular-nums hover:border-accent hover:text-foreground"
      >
        {pos.preco_atual != null ? formatBRL(pos.preco_atual) : "definir ✎"}
      </button>
      {auto && (
        <span aria-hidden title="Automático (Market Engine)" className="text-[10px] text-foreground/30">
          🔄
        </span>
      )}
      {pos.is_manual && pos.preco_atual != null && (
        <button
          type="button"
          title="Voltar ao automático (o worker volta a cotar)"
          onClick={() => revert.mutate(pos.asset_symbol)}
          className="text-[11px] text-foreground/40 hover:text-accent"
        >
          ↺
        </button>
      )}
    </span>
  );
}

// Valor atual editável: digita o valor TOTAL (ex.: o líquido do app do Tesouro/Nubank) e o
// preço unitário é recalculado (preço = valor / quantidade). Só editável com quantidade > 0.
function ValueCell({ pos }: { pos: Position }) {
  const setPrice = useSetManualPrice();
  const [editing, setEditing] = useState(false);
  const qty = pos.quantidade_net ?? 0;

  if (qty <= 0) {
    return (
      <span className="tabular-nums text-foreground/80">
        {pos.valor_atual != null ? formatBRL(pos.valor_atual) : "—"}
      </span>
    );
  }

  function commit(raw: string) {
    setEditing(false);
    const t = raw.trim();
    if (t === "") return;
    const total = parseDecimalInput(t);
    if (Number.isFinite(total) && total >= 0 && total !== pos.valor_atual) {
      setPrice.mutate({ symbol: pos.asset_symbol, price: total / qty });
    }
  }

  if (editing) {
    return (
      <InlineNumber
        initial={pos.valor_atual != null ? String(pos.valor_atual).replace(".", ",") : ""}
        onCommit={commit}
        onCancel={() => setEditing(false)}
      />
    );
  }
  return (
    <button
      type="button"
      title="Clique para informar o valor atual (o preço é recalculado)"
      onClick={() => setEditing(true)}
      className="cursor-text border-b border-dashed border-foreground/30 tabular-nums hover:border-accent hover:text-foreground"
    >
      {pos.valor_atual != null ? formatBRL(pos.valor_atual) : "definir ✎"}
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

// Rendimentos (dividendo/juros) por categoria — separados do ganho de capital. Onde o
// rendimento das caixinhas (juros sacados embutidos nos resgates) fica visível.
function IncomeCard() {
  const { data: income } = useIncome();
  if (!income || income.total <= 0) return null;
  return (
    <div className="rounded-2xl border border-border bg-muted/20 p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-foreground/60">
          💰 Rendimentos recebidos (dividendos / juros)
        </span>
        <span className="tabular-nums text-sm font-medium text-gain">
          {formatBRL(income.total)}
        </span>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
        {income.by_category.map((c) => (
          <div key={c.asset_category}>
            <div className="text-xs text-foreground/50">{c.asset_category}</div>
            <div className="tabular-nums text-foreground/80">{formatBRL(c.total)}</div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-foreground/40">
        Inclui FII/JCP da B3 e os juros realizados das caixinhas Nubank (o que rendeu e
        foi sacado ao longo do tempo).
      </p>
    </div>
  );
}

export default function PositionsPage() {
  const { data, isLoading, isError } = usePositions();
  // Cripto é um BLOCO (sleeve), renderizado como card abaixo — sai da tabela per-ativo, que
  // fica só com B3/RF/etc. (granularidade fiel). O backend já manda a linha-bloco em `data`,
  // então os totais consolidados a incluem; a tabela a filtra.
  const { data: sleeve } = useCryptoSleeve();

  const totalAtual = (data ?? []).reduce((s, p) => s + (p.valor_atual ?? 0), 0);
  const totalCusto = (data ?? []).reduce((s, p) => s + (p.custo_total ?? 0), 0);
  const totalResult = totalAtual - totalCusto;

  // Tabela per-ativo = só NÃO-cripto; cripto vira card. Grupos por maior posição.
  const groups = useMemo(() => {
    const map = new Map<string, Position[]>();
    for (const p of data ?? []) {
      if (p.asset_category === "Cripto") continue; // bloco no card, fora da tabela
      const arr = map.get(p.asset_category) ?? [];
      arr.push(p);
      map.set(p.asset_category, arr);
    }
    return [...map.entries()]
      .map(([category, rows]) => {
        const subtotalAtual = rows.reduce((s, p) => s + (p.valor_atual ?? 0), 0);
        const subtotalCusto = rows.reduce((s, p) => s + (p.custo_total ?? 0), 0);
        return {
          category,
          rows,
          subtotalAtual,
          subtotalCusto,
          subtotalResult: subtotalAtual - subtotalCusto,
        };
      })
      .sort((a, b) => b.subtotalAtual - a.subtotalAtual);
  }, [data]);

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
            {!isLoading && !isError && groups.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-foreground/50">
                  Nenhuma posição aberta.
                </td>
              </tr>
            )}
            {!isLoading &&
              !isError &&
              groups.map((g) => (
                <Fragment key={g.category}>
                  {/* cabeçalho da categoria */}
                  <tr className="border-t border-border bg-muted/50">
                    <td
                      colSpan={7}
                      className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-foreground/60"
                    >
                      {g.category}
                    </td>
                  </tr>

                  {/* ativos da categoria (só não-cripto; cripto é o card abaixo) */}
                  {g.rows.map((pos) => (
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
                        {pos.preco_medio != null ? formatBRL(pos.preco_medio) : "—"}
                      </td>
                      <td className="px-4 py-2.5 text-right text-foreground/80">
                        <PriceCell pos={pos} />
                      </td>
                      <td className="px-4 py-2.5 text-right text-foreground/80">
                        <ValueCell pos={pos} />
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <ResultCell pos={pos} />
                      </td>
                    </tr>
                  ))}

                  {/* subtotal da categoria */}
                  <tr className="border-t border-border bg-muted/30">
                    <td
                      colSpan={5}
                      className="px-4 py-2 text-right text-xs font-medium text-foreground/60"
                    >
                      Subtotal {g.category}
                    </td>
                    <td className="px-4 py-2 text-right font-medium tabular-nums text-foreground/80">
                      {formatBRL(g.subtotalAtual)}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {g.subtotalCusto > 0 ? (
                        <span
                          className={`font-medium tabular-nums ${
                            g.subtotalResult < 0 ? "text-loss" : "text-gain"
                          }`}
                        >
                          {formatBRL(g.subtotalResult)}{" "}
                          <span className="text-xs">
                            ({formatPercent((g.subtotalResult / g.subtotalCusto) * 100)})
                          </span>
                        </span>
                      ) : (
                        <span className="font-medium tabular-nums text-foreground/80">
                          {formatBRL(g.subtotalResult)}
                        </span>
                      )}
                    </td>
                  </tr>
                </Fragment>
              ))}
          </tbody>
        </table>
      </div>

      {sleeve && (sleeve.current_value_brl > 0 || sleeve.net_invested_brl > 0) && (
        <div className="rounded-2xl border border-border bg-muted/20 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wide text-foreground/60">
              🪙 Cripto (bloco)
            </span>
            <a href="/wallets" className="text-xs text-accent hover:underline">
              ver Carteiras →
            </a>
          </div>
          <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
            <div>
              <div className="text-xs text-foreground/50">Investido</div>
              <div className="tabular-nums text-foreground/80">
                {formatBRL(sleeve.net_invested_brl)}
              </div>
            </div>
            <div>
              <div className="text-xs text-foreground/50">Valor atual</div>
              <Money
                brl={sleeve.current_value_brl}
                usd={sleeve.current_value_usd}
                usdPartial={sleeve.usd_partial}
              />
            </div>
            <div>
              <div className="text-xs text-foreground/50">Resultado</div>
              <div className={`tabular-nums ${sleeve.resultado < 0 ? "text-loss" : "text-gain"}`}>
                {formatBRL(sleeve.resultado)}
              </div>
            </div>
            <div>
              <div className="text-xs text-foreground/50">XIRR</div>
              <div className={`tabular-nums ${(sleeve.xirr ?? 0) < 0 ? "text-loss" : "text-gain"}`}>
                {formatRate(sleeve.xirr)}
              </div>
            </div>
          </div>
          <p className="mt-2 text-xs text-foreground/40">
            Cripto entra como um bloco (quanto saiu do Nubank vs quanto tem hoje). O detalhe por
            moeda/carteira está em Carteiras Cripto.
          </p>
        </div>
      )}

      <IncomeCard />
    </div>
  );
}
