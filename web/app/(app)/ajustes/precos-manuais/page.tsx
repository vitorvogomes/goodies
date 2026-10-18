"use client";

// Ajustes › Preços manuais (Story 10.2 — FR-27, FR-35, UX-DR43): só os ativos sem fonte de mercado
// (a lista vem da API), com valor + data editáveis na linha — Enter grava, Esc reverte. O preço é
// gravado pelo `market` com is_manual (nunca expira; o worker não sobrescreve); ativo com cotação
// automática é recusado com "{Ativo} tem preço de mercado automático.".
import { useState } from "react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { formatUnitPrice, normalizeUnitPriceInput } from "@/lib/format";
import { currentDayBRT } from "@/lib/period";
import { type ManualPrice, useManualPrices, useSaveManualPrice } from "@/lib/portfolio";

const SAVE_FAILED = "Não foi possível salvar. Nada foi perdido. Tentar de novo.";

type Save = (price: string, asOf: string, onError: (message: string) => void) => void;

// A linha remonta (key) quando o preço gravado muda: a mutação fica na página, senão o retorno
// dela chegaria a uma linha já remontada.
function Row({ item, saving, onSave }: { item: ManualPrice; saving: boolean; onSave: Save }) {
  const shownPrice = item.price_brl != null ? formatUnitPrice(item.price_brl) : "";
  const shownDay = item.as_of ?? currentDayBRT();
  const [price, setPrice] = useState(shownPrice);
  const [day, setDay] = useState(shownDay);
  const [error, setError] = useState<string | null>(null);

  function commit() {
    const normalized = normalizeUnitPriceInput(price);
    if (normalized === null || normalized.startsWith("-") || !/^\d{4}-\d{2}-\d{2}$/.test(day)) {
      setError("Informe o preço (ex.: 5,25 ou 0,0042) e a data.");
      return;
    }
    if (day > currentDayBRT()) {
      setError("A data não pode ser depois de hoje.");
      return;
    }
    setError(null);
    onSave(normalized, day, setError);
  }

  function keys(e: React.KeyboardEvent) {
    if (e.key === "Enter") commit();
    if (e.key === "Escape") {
      setPrice(shownPrice);
      setDay(shownDay);
      setError(null);
    }
  }

  return (
    <tr className="border-t border-border">
      <th scope="row" className="px-4 py-2 text-left font-normal">
        {item.label}
        {!item.is_manual && item.price_brl == null && (
          <span className="block type-caption text-muted-foreground">sem preço ainda</span>
        )}
      </th>
      <td className="px-4 py-2 text-right">
        <Input
          aria-label={`Preço de ${item.label} (R$)`}
          inputMode="decimal"
          value={price}
          readOnly={saving}
          onChange={(e) => setPrice(e.target.value)}
          onKeyDown={keys}
          className="ml-auto h-8 w-32 type-num-table text-right"
        />
      </td>
      <td className="px-4 py-2 text-right">
        <Input
          aria-label={`Data do preço de ${item.label}`}
          type="date"
          max={currentDayBRT()}
          value={day}
          readOnly={saving}
          onChange={(e) => setDay(e.target.value)}
          onKeyDown={keys}
          className="ml-auto h-8 w-40"
        />
        {error && (
          <span role="alert" className="mt-1 block type-caption text-negative">
            {error}
          </span>
        )}
      </td>
    </tr>
  );
}

export default function PrecosManuaisPage() {
  const prices = useManualPrices();
  const save = useSaveManualPrice();
  const onSave = (item: ManualPrice): Save => (price, asOf, onError) =>
    save.mutate(
      { ticker: item.ticker, price, asOf },
      {
        onSuccess: () => toast(`Preço de ${item.label} salvo.`),
        onError: (err) => onError(apiErrorMessage(err instanceof ApiError ? err.detail : null, SAVE_FAILED)),
      },
    );
  if (prices.isError && !prices.data) {
    return <p className="type-body text-negative">Não foi possível carregar os preços manuais.</p>;
  }
  if (!prices.data) return <div className="h-40 animate-pulse rounded-lg border border-border bg-card" aria-hidden />;
  if (prices.data.length === 0) {
    return (
      <p className="rounded-lg border border-border bg-card p-card-padding type-body text-muted-foreground">
        Nenhum ativo sem fonte de mercado.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <p className="type-caption text-muted-foreground">
        Só ativos sem cotação automática. Enter grava, Esc reverte; o preço informado não expira.
      </p>
      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full type-body-sm">
          <caption className="sr-only">Preços manuais</caption>
          <thead className="bg-muted text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 text-left font-medium">Ativo</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Preço (R$)</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Data</th>
            </tr>
          </thead>
          <tbody>
            {prices.data.map((item) => (
              <Row
                key={`${item.ticker}-${item.price_brl}-${item.as_of}`}
                item={item}
                saving={save.isPending}
                onSave={onSave(item)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
