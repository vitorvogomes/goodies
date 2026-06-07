"use client";

// STORY-04-10 — Carteiras Cripto: saldos escaneados (on-chain/exchange) + entrada manual
// (Liquid confidencial) + posições DeFi. Valoração pelo preço do m3 (BRL e USD). Visão por rede.
import { type FormEvent, useState } from "react";

import { Button, Card, Field, Input, Select } from "@/components/ui";
import { formatBRL, formatUSD } from "@/lib/format";
import {
  useCreateDefi,
  useCreateManualPosition,
  useDefiPositions,
  useDeleteDefi,
  useDeleteManualPosition,
  useWalletPositions,
} from "@/lib/wallet";
import type { DefiPosition, WalletPosition } from "@/types/wallet";

function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function fmtQty(n: number): string {
  return n.toLocaleString("pt-BR", { maximumFractionDigits: 8 });
}

// Célula de dinheiro: BRL como principal, USD em mute logo abaixo. "—" sem preço.
function Money({ brl, usd }: { brl: number | null; usd: number | null }) {
  if (brl == null) return <span className="text-foreground/40">—</span>;
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="tabular-nums text-foreground/80">{formatBRL(brl)}</span>
      {usd != null && (
        <span className="tabular-nums text-[11px] text-foreground/40">{formatUSD(usd)}</span>
      )}
    </div>
  );
}

function StatusBadge({ p }: { p: WalletPosition }) {
  const base = "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs";
  if (p.is_manual) {
    return <span className={`${base} bg-accent/15 text-accent`}>✎ manual</span>;
  }
  if (p.price_brl == null) {
    return <span className={`${base} bg-loss/15 text-loss`}>✕ sem preço</span>;
  }
  if (p.stale) {
    return <span className={`${base} bg-warning/15 text-warning`}>⟳ desatualizado</span>;
  }
  return <span className={`${base} bg-gain/15 text-gain`}>↻ escaneado</span>;
}

interface ChainGroup {
  chain: string;
  items: WalletPosition[];
  subtotalBrl: number;
  subtotalUsd: number;
}

// Agrupa as posições por rede (chain), ordenadas, com subtotal BRL/USD por rede.
function groupByChain(positions: WalletPosition[]): ChainGroup[] {
  const map = new Map<string, WalletPosition[]>();
  for (const p of positions) {
    const arr = map.get(p.chain) ?? [];
    arr.push(p);
    map.set(p.chain, arr);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([chain, items]) => ({
      chain,
      items,
      subtotalBrl: items.reduce((s, p) => s + (p.value_brl ?? 0), 0),
      subtotalUsd: items.reduce((s, p) => s + (p.value_usd ?? 0), 0),
    }));
}

function PositionRow({ p }: { p: WalletPosition }) {
  const del = useDeleteManualPosition();
  return (
    <tr className="border-t border-border">
      <td className="px-4 py-2.5 font-medium text-foreground/90">{p.asset_symbol}</td>
      <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
        {fmtQty(p.quantity)}
      </td>
      <td className="px-4 py-2.5 text-right">
        <Money brl={p.price_brl} usd={p.price_usd} />
      </td>
      <td className="px-4 py-2.5 text-right">
        <Money brl={p.value_brl} usd={p.value_usd} />
      </td>
      <td className="px-4 py-2.5 text-right text-xs text-foreground/50">
        {p.is_manual ? "—" : fmtWhen(p.scanned_at)}
      </td>
      <td className="px-4 py-2.5 text-right">
        <StatusBadge p={p} />
      </td>
      <td className="px-4 py-2.5 text-right">
        {p.is_manual && (
          <button
            onClick={() => del.mutate({ chain: p.chain, asset_symbol: p.asset_symbol })}
            disabled={del.isPending}
            className="text-xs text-loss/80 hover:text-loss disabled:opacity-50"
            aria-label="Remover posição manual"
          >
            ✕
          </button>
        )}
      </td>
    </tr>
  );
}

function ManualForm() {
  const create = useCreateManualPosition();
  const [chain, setChain] = useState("liquid");
  const [asset, setAsset] = useState("L-BTC");
  const [qty, setQty] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const q = Number(qty.replace(",", "."));
    if (!Number.isFinite(q) || q < 0) {
      setError("Quantidade inválida.");
      return;
    }
    create.mutate(
      { chain: chain.trim(), asset_symbol: asset.trim(), quantity: q },
      { onSuccess: () => setQty(""), onError: () => setError("Falha ao salvar.") },
    );
  }

  return (
    <Card>
      <h2 className="mb-1 text-lg font-semibold text-foreground">Posição manual</h2>
      <p className="mb-4 text-xs text-foreground/50">
        Liquid (SideSwap) usa endereço confidencial e não é escaneável — informe L-BTC e
        L-USDT à mão. Valorados pelo preço do m3.
      </p>
      <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-4" noValidate>
        <Field label="Rede" htmlFor="m-chain">
          <Input id="m-chain" value={chain} onChange={(e) => setChain(e.target.value)} />
        </Field>
        <Field label="Ativo" htmlFor="m-asset">
          <Select id="m-asset" value={asset} onChange={(e) => setAsset(e.target.value)}>
            <option value="L-BTC">L-BTC</option>
            <option value="L-USDT">L-USDT</option>
          </Select>
        </Field>
        <Field label="Quantidade" htmlFor="m-qty">
          <Input
            id="m-qty"
            inputMode="decimal"
            placeholder="0,00"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
          />
        </Field>
        <div className="flex items-end">
          <Button type="submit" disabled={create.isPending} className="w-full">
            {create.isPending ? "Salvando…" : "Adicionar"}
          </Button>
        </div>
      </form>
      {error && <p className="mt-2 text-sm text-loss">{error}</p>}
    </Card>
  );
}

function DefiRow({ d }: { d: DefiPosition }) {
  const del = useDeleteDefi();
  return (
    <tr className="border-t border-border">
      <td className="px-4 py-2.5 font-medium text-foreground/90">{d.asset_symbol}</td>
      <td className="px-4 py-2.5 text-foreground/60">{d.protocol ?? "—"}</td>
      <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
        {fmtQty(d.balance)}
      </td>
      <td className="px-4 py-2.5 text-right">
        <Money brl={d.price_brl} usd={d.price_usd} />
      </td>
      <td className="px-4 py-2.5 text-right">
        <Money brl={d.value_brl} usd={d.value_usd} />
      </td>
      <td className="px-4 py-2.5 text-foreground/60">{d.maturity_date ?? "—"}</td>
      <td className="px-4 py-2.5 text-right">
        <button
          onClick={() => del.mutate(d.id)}
          disabled={del.isPending}
          className="text-xs text-loss/80 hover:text-loss disabled:opacity-50"
          aria-label="Remover posição DeFi"
        >
          ✕ remover
        </button>
      </td>
    </tr>
  );
}

function DefiSection() {
  const { data, isLoading, isError } = useDefiPositions();
  const create = useCreateDefi();
  const positions = data ?? [];
  const subtotalBrl = positions.reduce((s, d) => s + (d.value_brl ?? 0), 0);
  const subtotalUsd = positions.reduce((s, d) => s + (d.value_usd ?? 0), 0);
  const [asset, setAsset] = useState("");
  const [balance, setBalance] = useState("");
  const [protocol, setProtocol] = useState("");
  const [maturity, setMaturity] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const b = Number(balance.replace(",", "."));
    if (!asset.trim() || !Number.isFinite(b) || b < 0) {
      setError("Informe ativo e saldo válidos.");
      return;
    }
    create.mutate(
      {
        asset_symbol: asset.trim(),
        balance: b,
        protocol: protocol.trim() || null,
        maturity_date: maturity || null,
      },
      {
        onSuccess: () => {
          setAsset("");
          setBalance("");
          setProtocol("");
          setMaturity("");
        },
        onError: () => setError("Falha ao salvar."),
      },
    );
  }

  return (
    <Card>
      <h2 className="mb-1 text-lg font-semibold text-foreground">DeFi (manual)</h2>
      <p className="mb-4 text-xs text-foreground/50">
        Posições DeFi com vencimento (entrada manual). Valoradas pelo preço do m3 quando há
        fonte (YT-xSOL fica sem preço). Os alertas de vencimento leem destas.
      </p>

      <div className="mb-4 overflow-hidden rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-foreground/60">
            <tr>
              <th className="px-4 py-2.5 font-medium">Ativo</th>
              <th className="px-4 py-2.5 font-medium">Protocolo</th>
              <th className="px-4 py-2.5 text-right font-medium">Saldo</th>
              <th className="px-4 py-2.5 text-right font-medium">Preço</th>
              <th className="px-4 py-2.5 text-right font-medium">Valor</th>
              <th className="px-4 py-2.5 font-medium">Vencimento</th>
              <th className="px-4 py-2.5 text-right font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-foreground/50">
                  Carregando…
                </td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-loss">
                  Erro ao carregar DeFi.
                </td>
              </tr>
            )}
            {!isLoading && !isError && positions.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-foreground/50">
                  Nenhuma posição DeFi.
                </td>
              </tr>
            )}
            {positions.map((d) => (
              <DefiRow key={d.id} d={d} />
            ))}
          </tbody>
          {positions.length > 0 && (
            <tfoot>
              <tr className="border-t border-border bg-muted/30">
                <td className="px-4 py-2.5 text-xs font-medium text-foreground/60" colSpan={4}>
                  Subtotal DeFi
                </td>
                <td className="px-4 py-2.5 text-right">
                  <Money brl={subtotalBrl} usd={subtotalUsd} />
                </td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-5" noValidate>
        <Field label="Ativo" htmlFor="d-asset">
          <Input id="d-asset" value={asset} onChange={(e) => setAsset(e.target.value)} />
        </Field>
        <Field label="Saldo" htmlFor="d-balance">
          <Input
            id="d-balance"
            inputMode="decimal"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
          />
        </Field>
        <Field label="Protocolo" htmlFor="d-protocol">
          <Input id="d-protocol" value={protocol} onChange={(e) => setProtocol(e.target.value)} />
        </Field>
        <Field label="Vencimento" htmlFor="d-maturity">
          <Input
            id="d-maturity"
            type="date"
            value={maturity}
            onChange={(e) => setMaturity(e.target.value)}
          />
        </Field>
        <div className="flex items-end">
          <Button type="submit" disabled={create.isPending} className="w-full">
            {create.isPending ? "Salvando…" : "Adicionar"}
          </Button>
        </div>
      </form>
      {error && <p className="mt-2 text-sm text-loss">{error}</p>}
    </Card>
  );
}

export default function WalletsPage() {
  const { data, isLoading, isError } = useWalletPositions();
  const positions = data ?? [];
  const groups = groupByChain(positions);
  const totalBrl = positions.reduce((acc, p) => acc + (p.value_brl ?? 0), 0);
  const totalUsd = positions.reduce((acc, p) => acc + (p.value_usd ?? 0), 0);
  const staleCount = positions.filter((p) => !p.is_manual && (p.stale || p.price_brl == null))
    .length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-mono text-2xl font-semibold text-foreground">Carteiras Cripto</h1>
        <a href="/wallets/reconciliation">
          <Button variant="ghost">Reconciliação</Button>
        </a>
      </div>

      {positions.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-2 text-xs text-foreground/50">
          <span>
            Total valorado{" "}
            <span className="tabular-nums text-foreground/80">{formatBRL(totalBrl)}</span>
            {totalUsd > 0 && (
              <span className="tabular-nums text-foreground/40"> · {formatUSD(totalUsd)}</span>
            )}
          </span>
          <div className="flex flex-wrap gap-x-5 gap-y-1">
            <span>
              Posições <span className="tabular-nums text-foreground/70">{positions.length}</span>
            </span>
            <span>
              Sem preço/desatualizados{" "}
              <span
                className={`tabular-nums ${staleCount > 0 ? "text-warning" : "text-foreground/70"}`}
              >
                {staleCount}
              </span>
            </span>
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-foreground/60">
            <tr>
              <th className="px-4 py-2.5 font-medium">Ativo</th>
              <th className="px-4 py-2.5 text-right font-medium">Quantidade</th>
              <th className="px-4 py-2.5 text-right font-medium">Preço</th>
              <th className="px-4 py-2.5 text-right font-medium">Valor</th>
              <th className="px-4 py-2.5 text-right font-medium">Atualizado</th>
              <th className="px-4 py-2.5 text-right font-medium">Status</th>
              <th className="px-4 py-2.5 text-right font-medium"></th>
            </tr>
          </thead>
          {isLoading && (
            <tbody>
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-foreground/50">
                  Carregando…
                </td>
              </tr>
            </tbody>
          )}
          {isError && (
            <tbody>
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-loss">
                  Erro ao carregar carteiras.
                </td>
              </tr>
            </tbody>
          )}
          {!isLoading && !isError && positions.length === 0 && (
            <tbody>
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-foreground/50">
                  Nenhuma posição escaneada ainda.
                </td>
              </tr>
            </tbody>
          )}
          {!isLoading &&
            !isError &&
            groups.map((g) => (
              <tbody key={g.chain}>
                <tr className="border-t border-border bg-muted/30">
                  <td colSpan={7} className="px-4 py-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold uppercase tracking-wide text-foreground/60">
                        {g.chain}
                      </span>
                      <span className="text-xs">
                        <span className="tabular-nums text-foreground/70">
                          {formatBRL(g.subtotalBrl)}
                        </span>
                        {g.subtotalUsd > 0 && (
                          <span className="tabular-nums text-foreground/40">
                            {" "}
                            · {formatUSD(g.subtotalUsd)}
                          </span>
                        )}
                      </span>
                    </div>
                  </td>
                </tr>
                {g.items.map((p) => (
                  <PositionRow key={`${p.chain}:${p.asset_symbol}`} p={p} />
                ))}
              </tbody>
            ))}
        </table>
      </div>

      <ManualForm />
      <DefiSection />
    </div>
  );
}
