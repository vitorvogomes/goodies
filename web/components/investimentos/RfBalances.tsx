"use client";

// Ajustes › Preços manuais › Caixinhas e fundos (P28): o %CDI e o saldo que o app do banco mostra
// numa data — ou cotas × valor da cota, no fundo. Dali em diante o app rende o %CDI sobre esse saldo
// (as operações até a data saem da conta). Enter grava, Esc reverte.
import { useState } from "react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { formatBRL, formatDate, formatUnitPrice, normalizeMoneyInput, normalizeUnitPriceInput } from "@/lib/format";
import { currentDayBRT } from "@/lib/period";
import { type RfBalance, type RfBalanceIn, useRfBalances, useSaveRfBalance } from "@/lib/portfolio";

const SAVE_FAILED = "Não foi possível salvar. Nada foi perdido. Tentar de novo.";

type Save = (body: RfBalanceIn, onError: (message: string) => void) => void;

function Row({ item, saving, onSave }: { item: RfBalance; saving: boolean; onSave: Save }) {
  const shown = {
    pct: item.pct_cdi != null ? formatUnitPrice(String(item.pct_cdi)) : "",
    value: "",
    quotas: item.quotas != null ? formatUnitPrice(item.quotas) : "",
    quotaValue: item.quota_value != null ? formatUnitPrice(item.quota_value) : "",
    day: currentDayBRT(),
  };
  const [form, setForm] = useState(shown);
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof typeof shown) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  function commit() {
    const pct = form.pct ? normalizeUnitPriceInput(form.pct) : null;
    const value = form.value ? normalizeMoneyInput(form.value) : null;
    const quotas = form.quotas ? normalizeUnitPriceInput(form.quotas) : null;
    const quotaValue = form.quotaValue ? normalizeUnitPriceInput(form.quotaValue) : null;
    const byQuotas = quotas != null && quotaValue != null;
    if ((form.pct && pct == null) || (!byQuotas && value == null)) {
      setError("Informe o saldo (ex.: 14.246,65) ou as cotas e o valor da cota.");
      return;
    }
    if (form.day > currentDayBRT()) {
      setError("A data não pode ser depois de hoje.");
      return;
    }
    setError(null);
    onSave(
      {
        as_of: form.day,
        ...(byQuotas ? { quotas, quota_value: quotaValue } : { value: value! }),
        ...(pct ? { pct_cdi: pct } : {}),
      },
      setError,
    );
  }

  function keys(e: React.KeyboardEvent) {
    if (e.key === "Enter") commit();
    if (e.key === "Escape") {
      setForm(shown);
      setError(null);
    }
  }

  const input = "h-8 type-num-table text-right";
  return (
    <tr className="border-t border-border align-top">
      <th scope="row" className="px-4 py-2 text-left font-normal">
        {item.label}
        <span className="block type-caption text-muted-foreground">
          {item.anchor_date && item.value != null
            ? `Informado: ${formatBRL(Number(item.value))} em ${formatDate(item.anchor_date)}`
            : "Sem saldo informado: rende desde o primeiro aporte"}
        </span>
      </th>
      <td className="px-4 py-2">
        <Input aria-label={`% do CDI de ${item.label}`} inputMode="decimal" value={form.pct}
          readOnly={saving} onChange={set("pct")} onKeyDown={keys} className={`ml-auto w-20 ${input}`} />
      </td>
      <td className="px-4 py-2">
        <Input aria-label={`Saldo de ${item.label} (R$)`} inputMode="decimal" placeholder="saldo"
          value={form.value} readOnly={saving} onChange={set("value")} onKeyDown={keys}
          className={`ml-auto w-32 ${input}`} />
      </td>
      <td className="px-4 py-2">
        <div className="flex items-center justify-end gap-1">
          <Input aria-label={`Cotas de ${item.label}`} inputMode="decimal" placeholder="cotas"
            value={form.quotas} readOnly={saving} onChange={set("quotas")} onKeyDown={keys}
            className={`w-28 ${input}`} />
          <span className="text-muted-foreground" aria-hidden>×</span>
          <Input aria-label={`Valor da cota de ${item.label} (R$)`} inputMode="decimal" placeholder="valor da cota"
            value={form.quotaValue} readOnly={saving} onChange={set("quotaValue")} onKeyDown={keys}
            className={`w-28 ${input}`} />
        </div>
      </td>
      <td className="px-4 py-2 text-right">
        <Input aria-label={`Data do saldo de ${item.label}`} type="date" max={currentDayBRT()}
          value={form.day} readOnly={saving} onChange={set("day")} onKeyDown={keys} className="ml-auto h-8 w-40" />
        {error && (
          <span role="alert" className="mt-1 block type-caption text-negative">
            {error}
          </span>
        )}
      </td>
    </tr>
  );
}

export function RfBalances() {
  const rows = useRfBalances();
  const save = useSaveRfBalance();
  if (!rows.data || rows.data.length === 0) return null;
  const onSave = (item: RfBalance): Save => (body, onError) =>
    save.mutate(
      { ticker: item.ticker, body },
      {
        onSuccess: () => toast(`Saldo de ${item.label} salvo.`),
        onError: (err) => onError(apiErrorMessage(err instanceof ApiError ? err.detail : null, SAVE_FAILED)),
      },
    );
  return (
    <section className="space-y-2" aria-labelledby="rf-balances">
      <h2 id="rf-balances" className="type-section-title">Caixinhas e fundos (CDI)</h2>
      <p className="type-caption text-muted-foreground">
        Informe o saldo que o app do banco mostra, ou cotas × valor da cota no fundo. Dali em diante o app rende o
        % do CDI sobre esse saldo. Enter grava, Esc reverte.
      </p>
      <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card">
        <table className="w-full type-body-sm">
          <caption className="sr-only">Saldo informado da renda fixa pelo CDI</caption>
          <thead className="bg-muted text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 text-left font-medium">Ativo</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">% do CDI</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Saldo (R$)</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">ou cotas × valor da cota</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Data</th>
            </tr>
          </thead>
          <tbody>
            {rows.data.map((item) => (
              <Row
                key={`${item.ticker}-${item.anchor_date}-${item.value}-${item.pct_cdi}`}
                item={item}
                saving={save.isPending}
                onSave={onSave(item)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
