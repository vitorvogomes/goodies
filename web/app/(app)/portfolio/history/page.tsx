"use client";

// STORY-02-14 — histórico de operações com filtros (tipo, ativo, período).
import { useState } from "react";

import { Field, Input, Select } from "@/components/ui";
import { formatBRL, formatDate } from "@/lib/format";
import { useAssetOperations } from "@/lib/portfolio";
import type { OperationTipo } from "@/types/portfolio";

const TIPOS: OperationTipo[] = [
  "compra",
  "venda",
  "dividendo",
  "juros",
  "aporte",
  "resgate",
];

const TIPO_COLOR: Record<OperationTipo, string> = {
  compra: "text-accent",
  aporte: "text-accent",
  venda: "text-gain",
  resgate: "text-gain",
  dividendo: "text-gain",
  juros: "text-gain",
};

export default function HistoryPage() {
  const [symbol, setSymbol] = useState("");
  const [tipo, setTipo] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const { data, isLoading, isError } = useAssetOperations({
    asset_symbol: symbol || undefined,
    tipo: (tipo || undefined) as OperationTipo | undefined,
    data_from: from || undefined,
    data_to: to || undefined,
  });

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-2xl font-semibold text-foreground">
        Histórico de operações
      </h1>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Ativo" htmlFor="f-symbol">
          <Input
            id="f-symbol"
            placeholder="PETR4F…"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
        </Field>
        <Field label="Tipo" htmlFor="f-tipo">
          <Select id="f-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="De" htmlFor="f-from">
          <Input id="f-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </Field>
        <Field label="Até" htmlFor="f-to">
          <Input id="f-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </Field>
      </div>

      <div className="overflow-hidden rounded-2xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-foreground/60">
            <tr>
              <th className="px-4 py-2.5 font-medium">Data</th>
              <th className="px-4 py-2.5 font-medium">Ativo</th>
              <th className="px-4 py-2.5 font-medium">Tipo</th>
              <th className="px-4 py-2.5 text-right font-medium">Qtd.</th>
              <th className="px-4 py-2.5 text-right font-medium">Preço unit.</th>
              <th className="px-4 py-2.5 text-right font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-foreground/50">
                  Carregando…
                </td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-loss">
                  Erro ao carregar operações.
                </td>
              </tr>
            )}
            {!isLoading && !isError && (data?.length ?? 0) === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-foreground/50">
                  Nenhuma operação encontrada.
                </td>
              </tr>
            )}
            {(data ?? []).map((op) => (
              <tr key={op.id} className="border-t border-border">
                <td className="px-4 py-2.5 tabular-nums text-foreground/80">
                  {formatDate(op.data_operacao)}
                </td>
                <td className="px-4 py-2.5 font-medium text-foreground/90">
                  {op.asset_symbol}
                  <span className="ml-2 text-xs text-foreground/40">{op.asset_category}</span>
                </td>
                <td className={`px-4 py-2.5 ${TIPO_COLOR[op.tipo]}`}>{op.tipo}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                  {op.quantidade}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                  {formatBRL(op.valor_unitario)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                  {formatBRL(op.quantidade * op.valor_unitario)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-foreground/50">
        {data?.length ?? 0} operação(ões)
      </p>
    </div>
  );
}
