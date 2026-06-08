"use client";

// STORY-04-10 — Carteiras Cripto: saldos escaneados (on-chain/exchange) + entrada manual
// (Liquid confidencial) + posições DeFi. Valoração pelo preço do m3 (BRL e USD). Visão por rede.
import { type FormEvent, useRef, useState } from "react";

import { Badge, Button, Card, Field, Input, Select } from "@/components/ui";
import { fmtQty, fmtWhen, formatBRL, formatUSD, parseDecimalInput } from "@/lib/format";
import {
  useCreateDefi,
  useCreateManualPosition,
  useDefiPositions,
  useDeleteDefi,
  useDeleteManualPosition,
  useUpdateDefi,
  useWalletPositions,
} from "@/lib/wallet";
import type { DefiPosition, WalletPosition } from "@/types/wallet";

// Número editável inline (clique no valor → input; Enter salva, Esc cancela). Usado para
// editar a quantidade de posições manuais (Liquid) e o saldo das posições DeFi.
function EditableNumber({
  value,
  onSave,
  pending,
  error = false,
}: {
  value: number;
  onSave: (v: number) => void;
  pending: boolean;
  error?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  // o Enter chama commit() e desmonta o input → o onBlur dispararia commit() de novo;
  // este flag (resetado ao reentrar em edição) garante uma única gravação.
  const committed = useRef(false);

  function commit() {
    if (committed.current) return;
    committed.current = true;
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed === "") return; // campo vazio → não salva (evita zerar o saldo por engano)
    const n = parseDecimalInput(trimmed);
    if (Number.isFinite(n) && n >= 0 && n !== value) onSave(n);
  }

  if (!editing) {
    return (
      <button
        onClick={() => {
          setDraft(String(value).replace(".", ","));
          committed.current = false;
          setEditing(true);
        }}
        className="group inline-flex items-center gap-1 tabular-nums text-foreground/80 hover:text-foreground"
        title="Editar"
      >
        {pending ? "…" : fmtQty(value)}
        <span
          className={
            error
              ? "text-[10px] text-loss"
              : "text-[10px] text-foreground/30 group-hover:text-accent"
          }
          title={error ? "Falha ao salvar — tente de novo" : "Editar"}
        >
          {error ? "⚠" : "✎"}
        </span>
      </button>
    );
  }

  return (
    <input
      autoFocus
      inputMode="decimal"
      value={draft}
      disabled={pending}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
        else if (e.key === "Escape") setEditing(false);
      }}
      className="w-28 rounded border border-border bg-muted/40 px-2 py-1 text-right tabular-nums text-foreground outline-none focus:border-accent"
    />
  );
}

// Célula de dinheiro: BRL como principal, USD em mute logo abaixo. "—" sem preço.
// `usdPartial` marca com "*" um total USD que subestima (algum item sem preço USD).
function Money({
  brl,
  usd,
  usdPartial = false,
}: {
  brl: number | null;
  usd: number | null;
  usdPartial?: boolean;
}) {
  if (brl == null) return <span className="text-foreground/40">—</span>;
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="tabular-nums text-foreground/80">{formatBRL(brl)}</span>
      {usd != null && (
        <span className="tabular-nums text-[11px] text-foreground/40">
          {formatUSD(usd)}
          {usdPartial && "*"}
        </span>
      )}
    </div>
  );
}

const MANUAL_STALE_DAYS = 7; // saldo manual mais velho que isso pede revisão

function ageDays(iso: string): number {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 0;
  return Math.max(0, Math.floor((Date.now() - d.getTime()) / 86_400_000));
}

function StatusBadge({ p }: { p: WalletPosition }) {
  // Manuais não se atualizam sozinhos (Neobankless, SideSwap): mostrar a idade e
  // alertar quando o valor está velho o bastante para revisar.
  if (p.is_manual) {
    const days = ageDays(p.scanned_at);
    return days >= MANUAL_STALE_DAYS ? (
      <Badge tone="warning">✎ manual · {days}d</Badge>
    ) : (
      <Badge tone="accent">✎ manual</Badge>
    );
  }
  if (p.price_brl == null) return <Badge tone="loss">✕ sem preço</Badge>;
  if (p.stale) return <Badge tone="warning">⟳ desatualizado</Badge>;
  return <Badge tone="gain">↻ escaneado</Badge>;
}

interface ValueSum {
  brl: number;
  usd: number;
  // false quando algum item tem BRL mas USD nulo → o total USD subestima (marcado com *)
  usdComplete: boolean;
}

// Soma valores BRL/USD; sinaliza quando o USD está incompleto (preço só em BRL).
function sumValues(items: Array<{ value_brl: number | null; value_usd: number | null }>): ValueSum {
  let brl = 0;
  let usd = 0;
  let usdComplete = true;
  for (const p of items) {
    brl += p.value_brl ?? 0;
    usd += p.value_usd ?? 0;
    if (p.value_brl != null && p.value_usd == null) usdComplete = false;
  }
  return { brl, usd, usdComplete };
}

interface ChainGroup {
  chain: string;
  items: WalletPosition[];
  sum: ValueSum;
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
    .map(([chain, items]) => ({ chain, items, sum: sumValues(items) }));
}

// USD do subtotal/total com marcador "*" quando incompleto (algum item sem USD).
function UsdSuffix({ sum }: { sum: ValueSum }) {
  if (sum.usd <= 0) return null;
  return (
    <span className="tabular-nums text-foreground/40">
      {" "}
      · {formatUSD(sum.usd)}
      {!sum.usdComplete && "*"}
    </span>
  );
}

function PositionRow({ p }: { p: WalletPosition }) {
  const del = useDeleteManualPosition();
  const upd = useCreateManualPosition(); // POST manual = upsert → edita a quantidade
  return (
    <tr className="border-t border-border">
      <td className="px-4 py-2.5 font-medium text-foreground/90">{p.asset_symbol}</td>
      <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
        {p.is_manual ? (
          <EditableNumber
            value={p.quantity}
            pending={upd.isPending}
            error={upd.isError}
            onSave={(v) =>
              upd.mutate({ chain: p.chain, asset_symbol: p.asset_symbol, quantity: v })
            }
          />
        ) : (
          fmtQty(p.quantity)
        )}
      </td>
      <td className="px-4 py-2.5 text-right">
        <Money brl={p.price_brl} usd={p.price_usd} />
      </td>
      <td className="px-4 py-2.5 text-right">
        <Money brl={p.value_brl} usd={p.value_usd} />
      </td>
      <td className="px-4 py-2.5 text-right text-xs text-foreground/50">
        {fmtWhen(p.scanned_at)}
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
    const q = parseDecimalInput(qty);
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
        L-USDT à mão. Valorados pelo preço do m3. Para alterar uma quantidade já lançada,
        clique no valor na tabela acima (✎).
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
  const upd = useUpdateDefi();
  return (
    <tr className="border-t border-border">
      <td className="px-4 py-2.5 font-medium text-foreground/90">{d.asset_symbol}</td>
      <td className="px-4 py-2.5 text-foreground/60">{d.protocol ?? "—"}</td>
      <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
        <EditableNumber
          value={d.balance}
          pending={upd.isPending}
          error={upd.isError}
          onSave={(v) => upd.mutate({ id: d.id, balance: v })}
        />
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
  const sum = sumValues(positions);
  const [asset, setAsset] = useState("");
  const [balance, setBalance] = useState("");
  const [protocol, setProtocol] = useState("");
  const [maturity, setMaturity] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const b = parseDecimalInput(balance);
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
        fonte (YT-xSOL fica sem preço). Clique no saldo para editar (✎). Os alertas de
        vencimento leem destas.
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
                  <Money brl={sum.brl} usd={sum.usd} usdPartial={!sum.usdComplete} />
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
  const total = sumValues(positions);
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
            <span className="tabular-nums text-foreground/80">{formatBRL(total.brl)}</span>
            <UsdSuffix sum={total} />
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
                          {formatBRL(g.sum.brl)}
                        </span>
                        <UsdSuffix sum={g.sum} />
                      </span>
                    </div>
                  </td>
                </tr>
                {g.items.map((p) => (
                  <PositionRow
                    key={`${p.chain}:${p.asset_symbol}:${p.wallet_address}`}
                    p={p}
                  />
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
