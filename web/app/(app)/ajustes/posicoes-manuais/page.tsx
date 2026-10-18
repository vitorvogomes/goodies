"use client";

// Ajustes › Posições manuais (Story 7.8 — FR-27, FR-35): o que nenhum scan alcança — a carteira
// manual (L-BTC/L-USDT da SideSwap, Liquid confidencial) e as posições DeFi (hyUSD, xSOL…) com o
// vencimento. Criar e editar no Formulário em painel lateral; grava pela engine wallet.
import { useRef, useState } from "react";
import { toast } from "sonner";

import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { RowActions } from "@/components/data/RowActions";
import { StatusBadge } from "@/components/data/StatusBadge";
import { FormField, SideForm } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fmtQty, formatDate, parseDecimalInput } from "@/lib/format";
import { currentDayBRT } from "@/lib/period";
import {
  useCreateDefi,
  useCreateManualPosition,
  useDeleteDefi,
  useDeleteManualPosition,
  useManualPositions,
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
  const [touched, setTouched] = useState(false);
  const [failed, setFailed] = useState(false);
  const saving = createWallet.isPending || createDefi.isPending || updateDefi.isPending;
  const errors = {
    asset: asset.trim() ? null : "Informe o ativo.",
    where: kind === "carteira" && !where.trim() ? "Informe a rede (ex.: liquid)." : null,
    amount: qty(amount) === null ? "Informe a quantidade (ex.: 0,0123)." : null,
    day: kind === "carteira" && day > currentDayBRT() ? "A data não pode ser depois de hoje." : null,
  };
  // Qualquer campo conta como alteração (só a data ou só o vencimento também salvam).
  const dirty =
    asset !== (item?.asset_symbol ?? "") ||
    amount !== (item ? qtyText(item.quantity) : "") ||
    where !== (item ? (item.chain ?? item.protocol ?? "") : "") ||
    day !== (item?.as_of ?? currentDayBRT()) ||
    maturity !== (item?.maturity_date ?? "");

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
    } else if (item) {
      updateDefi.mutate(
        { id: item.id, asset_symbol: asset.trim(), balance: quantity, protocol: where.trim() || null, maturity_date: maturity || null },
        done,
      );
    } else {
      createDefi.mutate(
        { asset_symbol: asset.trim(), balance: quantity, protocol: where.trim() || null, maturity_date: maturity || null },
        done,
      );
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
        <FormField id="manual-venc" label="Vencimento">
          <Input id="manual-venc" type="date" value={maturity} onChange={(e) => setMaturity(e.target.value)} className="w-44" />
        </FormField>
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
    { id: "tipo", header: "Tipo", value: (i) => (i.kind === "carteira" ? "Carteira" : "DeFi") },
    { id: "onde", header: "Rede / protocolo", value: (i) => i.chain ?? i.protocol ?? "—" },
    { id: "qtd", header: "Quantidade", value: (i) => i.quantity, numeric: true, cell: (i) => fmtQty(i.quantity) },
    { id: "data", header: "Data", value: (i) => i.as_of, cell: (i) => (i.as_of ? formatDate(i.as_of) : "—") },
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
