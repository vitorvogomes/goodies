"use client";

// Ajustes › Posições manuais (Story 7.8 — FR-27, FR-35): o que nenhum scan alcança — a carteira
// manual (L-BTC/L-USDT da SideSwap, Liquid confidencial) e as posições DeFi (hyUSD, xSOL…) com o
// vencimento. Criar e editar no Formulário em painel lateral; grava pela engine wallet. Desde a v2.2
// a posição DeFi é atualizada pelo saldo em US$ que o protocolo mostra (+ APY opcional), não por
// preço manual do token; a tabela mostra o valor de hoje em R$ e US$.
import { useRef, useState } from "react";
import { toast } from "sonner";

import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { MoneyDual } from "@/components/data/MoneyDual";
import { RowActions } from "@/components/data/RowActions";
import { StatusBadge } from "@/components/data/StatusBadge";
import { FormField, SideForm } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fmtQty, formatBRL, formatDate, formatPercent, formatUSD, normalizeMoneyInput, parseDecimalInput } from "@/lib/format";
import { currentDayBRT } from "@/lib/period";
import {
  useCreateDefi,
  useCreateManualPosition,
  useDeleteDefi,
  useDeleteManualPosition,
  useManualPositions,
  useSetDefiBalance,
  useUpdateDefi,
} from "@/lib/wallet";
import type { ManualItem } from "@/types/wallet";

type Kind = ManualItem["kind"];

// "0.5", "0,5" e "1.234,5" (parseDecimalInput); o valor salvo volta sem milhar nem expoente.
function qty(raw: string): number | null {
  const n = parseDecimalInput(raw);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

function qtyText(n: number): string {
  return n.toLocaleString("pt-BR", { maximumFractionDigits: 8, useGrouping: false });
}

// Saldo e APY: "60,25", "US$ 1.234,50", "12.5" → decimal em texto (2 casas); vazio/ inválido → null.
function money(raw: string): string | null {
  return normalizeMoneyInput(raw.replace(/US\$|\$/g, ""));
}

function usdText(n: number): string {
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: false });
}

function ManualForm({ item, onClose }: { item: ManualItem | null; onClose: () => void }) {
  const createWallet = useCreateManualPosition();
  const createDefi = useCreateDefi();
  const updateDefi = useUpdateDefi();
  const [kind, setKind] = useState<Kind>(item?.kind ?? "carteira");
  const [asset, setAsset] = useState(item?.asset_symbol ?? "");
  const [where, setWhere] = useState(item ? (item.chain ?? item.protocol ?? "") : "");
  const [amount, setAmount] = useState(item ? qtyText(item.quantity) : "");
  const [day, setDay] = useState(item?.as_of ?? currentDayBRT());
  const [maturity, setMaturity] = useState(item?.maturity_date ?? "");
  // v2.2: DeFi pelo saldo em US$ que o protocolo mostra (+ APY), no lugar do preço manual
  const [usd, setUsd] = useState(item?.anchor ? usdText(item.anchor.value_usd) : "");
  const [apy, setApy] = useState(item?.anchor?.apy != null ? usdText(item.anchor.apy) : "");
  // a data do saldo começa na do saldo informado: mudar só o APY não re-data o saldo para hoje
  // (o que apagaria o rendimento desde a data dele — review v2.2)
  const [usdDay, setUsdDay] = useState(item?.anchor?.as_of ?? currentDayBRT());
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const setBalance = useSetDefiBalance();
  const saving = createWallet.isPending || createDefi.isPending || updateDefi.isPending || setBalance.isPending;
  const balanceDirty =
    kind === "defi" &&
    (usd !== (item?.anchor ? usdText(item.anchor.value_usd) : "") ||
      apy !== (item?.anchor?.apy != null ? usdText(item.anchor.apy) : "") ||
      (usd !== "" && usdDay !== (item?.anchor?.as_of ?? currentDayBRT())));
  const errors = {
    asset: asset.trim() ? null : "Informe o ativo.",
    where: kind === "carteira" && !where.trim() ? "Informe a rede (ex.: liquid)." : null,
    amount: qty(amount) === null ? "Informe a quantidade (ex.: 0,0123)." : null,
    day: kind === "carteira" && day > currentDayBRT() ? "A data não pode ser depois de hoje." : null,
    usd: kind === "defi" && usd.trim() && money(usd) === null ? "Informe o saldo em US$ (ex.: 60,25)." : null,
    apy:
      kind === "defi" && apy.trim() && (money(apy) === null || Number(money(apy)) <= -100)
        ? "Informe o APY em % ao ano (ex.: 12,5)."
        : null,
    usdDay: kind === "defi" && usdDay > currentDayBRT() ? "A data não pode ser depois de hoje." : null,
  };
  // Qualquer campo conta como alteração (só a data ou só o vencimento também salvam).
  const dirty =
    asset !== (item?.asset_symbol ?? "") ||
    amount !== (item ? qtyText(item.quantity) : "") ||
    where !== (item ? (item.chain ?? item.protocol ?? "") : "") ||
    day !== (item?.as_of ?? currentDayBRT()) ||
    maturity !== (item?.maturity_date ?? "") ||
    balanceDirty;

  function submit() {
    setTouched(true);
    const quantity = qty(amount);
    if (Object.values(errors).some(Boolean) || quantity === null) return;
    setFailed(false);
    const done = {
      onSuccess: () => {
        toast(item ? "Posição salva." : "Posição cadastrada.");
        onClose();
      },
      onError: () => setFailed(true),
    };
    if (kind === "carteira") {
      createWallet.mutate({ chain: where.trim(), asset_symbol: asset.trim(), quantity, as_of: day || null }, done);
    } else {
      const body = { asset_symbol: asset.trim(), balance: quantity, protocol: where.trim() || null, maturity_date: maturity || null };
      const value = money(usd);
      // a posição primeiro (quantidade nova muda o preço), depois o saldo em US$, se mudou
      const withBalance = (id: string) =>
        balanceDirty && value !== null
          ? setBalance.mutate({ id, as_of: usdDay, value_usd: value, apy: money(apy) }, done)
          : done.onSuccess();
      if (item) updateDefi.mutate({ id: item.id, ...body }, { onSuccess: () => withBalance(item.id), onError: done.onError });
      else
        createDefi.mutate(body, {
          onSuccess: (created) => withBalance((created as { id: string }).id),
          onError: done.onError,
        });
    }
  }

  const shown = (k: keyof typeof errors) => (touched ? errors[k] : null);
  return (
    <SideForm
      open
      title={item ? "Editar posição manual" : "Nova posição manual"}
      description="Entra no bloco cripto e no patrimônio com o Selo manual e a data informada."
      dirty={dirty}
      saving={saving}
      failed={failed}
      onClose={onClose}
      onSubmit={submit}
    >
      {!item && (
        <FormField id="manual-tipo" label="Tipo">
          <select
            id="manual-tipo"
            value={kind}
            onChange={(e) => setKind(e.target.value as Kind)}
            className="h-9 w-full rounded-md border border-input bg-background px-3 type-body"
          >
            <option value="carteira">Carteira (sem scan, ex.: SideSwap)</option>
            <option value="defi">Posição DeFi (com vencimento)</option>
          </select>
        </FormField>
      )}
      <FormField id="manual-ativo" label="Ativo" error={shown("asset")}>
        <Input id="manual-ativo" value={asset} disabled={item?.kind === "carteira"} onChange={(e) => setAsset(e.target.value)} />
      </FormField>
      <FormField id="manual-onde" label={kind === "carteira" ? "Rede" : "Protocolo"} error={shown("where")}>
        <Input id="manual-onde" value={where} disabled={item?.kind === "carteira"} onChange={(e) => setWhere(e.target.value)} />
      </FormField>
      <FormField id="manual-qtd" label="Quantidade" error={shown("amount")}>
        <Input id="manual-qtd" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} className="type-num-body" />
      </FormField>
      {kind === "carteira" ? (
        <FormField id="manual-data" label="Data em que você viu" error={shown("day")}>
          <Input id="manual-data" type="date" max={currentDayBRT()} value={day} onChange={(e) => setDay(e.target.value)} className="w-44" />
        </FormField>
      ) : (
        <>
          <FormField id="manual-venc" label="Vencimento">
            <Input id="manual-venc" type="date" value={maturity} onChange={(e) => setMaturity(e.target.value)} className="w-44" />
          </FormField>
          <fieldset className="space-y-3 rounded-md border border-border p-3">
            <legend className="px-1 type-section-title">Saldo em US$</legend>
            <p className="type-body-sm text-muted-foreground">
              O valor que o protocolo mostra na data abaixo (com a quantidade de hoje da posição). Com o APY, ele rende
              por dia até você informar de novo; o R$ segue a cotação do dólar. Substitui o preço manual do token; não
              vale para token com cotação de mercado (SOL, USDC…).
            </p>
            <FormField id="manual-usd" label="Saldo (US$)" error={shown("usd")}>
              <Input id="manual-usd" inputMode="decimal" placeholder="ex.: 60,25" value={usd} onChange={(e) => setUsd(e.target.value)} className="type-num-body" />
            </FormField>
            <FormField id="manual-apy" label="APY (% a.a., opcional)" error={shown("apy")}>
              <Input id="manual-apy" inputMode="decimal" placeholder="ex.: 12,5" value={apy} onChange={(e) => setApy(e.target.value)} className="w-32 type-num-body" />
            </FormField>
            <FormField id="manual-usd-data" label="Data do saldo" error={shown("usdDay")}>
              <Input id="manual-usd-data" type="date" max={currentDayBRT()} value={usdDay} onChange={(e) => setUsdDay(e.target.value)} className="w-44" />
            </FormField>
          </fieldset>
        </>
      )}
    </SideForm>
  );
}

export default function PosicoesManuaisPage() {
  const items = useManualPositions();
  const removeWallet = useDeleteManualPosition();
  const removeDefi = useDeleteDefi();
  const [editing, setEditingState] = useState<ManualItem | "nova" | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const setEditing = (next: ManualItem | "nova" | null) => {
    if (next) opener.current = document.activeElement as HTMLElement | null;
    setEditingState(next);
    if (!next) requestAnimationFrame(() => opener.current?.focus());
  };
  const remove = (i: ManualItem) => {
    const done = { onSuccess: () => toast("Posição excluída."), onError: () => toast("Não foi possível excluir. Nada foi perdido.") };
    if (i.kind === "carteira" && i.chain) removeWallet.mutate({ chain: i.chain, asset_symbol: i.asset_symbol }, done);
    else removeDefi.mutate(i.id, done);
  };

  const columns: DataColumn<ManualItem>[] = [
    {
      id: "ativo",
      header: "Ativo",
      value: (i) => i.asset_symbol,
      cell: (i) => (
        <span className="inline-flex items-center gap-2">
          {i.asset_symbol}
          <StatusBadge>manual</StatusBadge>
          {!i.is_active && <span className="type-caption text-muted-foreground">inativa</span>}
        </span>
      ),
    },
    { id: "tipo", header: "Tipo", value: (i) => (i.kind === "carteira" ? "Carteira" : "DeFi"), mobile: "meta" },
    { id: "onde", header: "Rede / protocolo", value: (i) => i.chain ?? i.protocol ?? "—", mobile: "meta" },
    { id: "qtd", header: "Quantidade", value: (i) => i.quantity, numeric: true, cell: (i) => fmtQty(i.quantity) },
    {
      id: "valor",
      header: "Valor hoje",
      value: (i) => i.value_brl ?? null,
      numeric: true,
      mobile: "aside",
      cell: (i) =>
        i.value_brl != null ? (
          <MoneyDual brl={formatBRL(i.value_brl)} usd={i.value_usd} />
        ) : (
          <span className="text-muted-foreground">sem preço</span>
        ),
    },
    {
      id: "saldo",
      header: "Saldo informado",
      value: (i) => i.anchor?.value_usd ?? null,
      cell: (i) =>
        i.anchor ? (
          <span className="type-body-sm">
            <span className="type-num-table">{formatUSD(i.anchor.value_usd)}</span>
            {i.anchor.apy != null && ` · ${formatPercent(i.anchor.apy)} a.a.`}
            <span className="block type-caption text-muted-foreground">em {formatDate(i.anchor.as_of)}</span>
          </span>
        ) : i.kind === "defi" ? (
          <span className="type-caption text-muted-foreground">sem saldo informado</span>
        ) : (
          "—"
        ),
    },
    { id: "data", header: "Data", value: (i) => i.as_of, cell: (i) => (i.as_of ? formatDate(i.as_of) : "—"), detailOnly: true },
    {
      id: "vencimento",
      header: "Vencimento",
      value: (i) => i.maturity_date,
      cell: (i) => (i.maturity_date ? formatDate(i.maturity_date) : "—"),
    },
    {
      id: "acoes",
      header: "Ações",
      value: () => null,
      sortable: false,
      actions: true,
      cell: (i) => (
        <RowActions subject={i.asset_symbol} onEdit={() => setEditing(i)} onDelete={() => remove(i)} />
      ),
    },
  ];

  if (items.isError) return <p className="type-body text-negative">Não foi possível carregar as posições manuais.</p>;
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setEditing("nova")}>Nova posição manual</Button>
      </div>
      <DataTable
        tableId="ajustes-posicoes-manuais"
        caption="Posições manuais"
        data={items.data ?? []}
        columns={columns}
        getRowId={(i) => `${i.kind}:${i.id}`}
        empty={items.isLoading ? "Carregando…" : "Nenhuma posição manual. Cadastre o que nenhum scan alcança."}
      />
      {editing && (
        <ManualForm
          key={editing === "nova" ? "nova" : `${editing.kind}:${editing.id}`}
          item={editing === "nova" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
