"use client";

// Operações (Story 10.6 — o substituto da tela v1 /portfolio/history): as operações dos ativos com
// os filtros (ativo por trecho, tipo, período), recolhidas por padrão. O total de cada operação vem
// da API (AD-4).
import { ChevronRightIcon } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { fmtQty, formatBRL, formatDate, formatUnitPrice } from "@/lib/format";
import { useOperations } from "@/lib/positions";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

const TIPOS = ["compra", "venda", "aporte", "resgate", "dividendo", "juros"];

function Operations() {
  const [ativo, setAtivo] = useState("");
  const [tipo, setTipo] = useState("");
  const [de, setDe] = useState("");
  const [ate, setAte] = useState("");
  const ops = useOperations({ ativo: useDebounced(ativo.trim()), tipo, de, ate });
  const field = "space-y-1 type-caption text-muted-foreground";
  return (
    <div className="space-y-3">
      <div className="grid gap-card-gap sm:grid-cols-2 lg:grid-cols-4">
        <label className={field}>
          Ativo
          <Input value={ativo} placeholder="busca por trecho: petr, nubank…" onChange={(e) => setAtivo(e.target.value)} />
        </label>
        <label className={field}>
          Tipo
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-2 type-body-sm text-foreground"
          >
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className={field}>
          De
          <Input type="date" value={de} onChange={(e) => setDe(e.target.value)} />
        </label>
        <label className={field}>
          Até
          <Input type="date" value={ate} onChange={(e) => setAte(e.target.value)} />
        </label>
      </div>
      <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card">
        <table className="w-full type-body-sm">
          <caption className="sr-only">Operações dos ativos</caption>
          <thead className="bg-muted text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 text-left font-medium">Data</th>
              <th scope="col" className="px-4 py-2 text-left font-medium">Ativo</th>
              <th scope="col" className="px-4 py-2 text-left font-medium">Tipo</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Qtd.</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Preço unit.</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {ops.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  Carregando…
                </td>
              </tr>
            )}
            {ops.isError && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-negative">
                  Não foi possível carregar as operações.
                </td>
              </tr>
            )}
            {ops.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  Nenhuma operação com esses filtros.
                </td>
              </tr>
            )}
            {(ops.data ?? []).map((op) => (
              <tr key={op.id}>
                <td className="px-4 py-2 type-num-table">{formatDate(op.data_operacao)}</td>
                <td className="px-4 py-2">
                  <span className="type-num-table">{op.asset_symbol}</span>
                  <span className="ml-2 type-caption text-muted-foreground">{op.asset_category}</span>
                </td>
                <td className="px-4 py-2">{op.tipo}</td>
                <td className="px-4 py-2 text-right type-num-table">{fmtQty(Number(op.quantidade))}</td>
                <td className="px-4 py-2 text-right type-num-table">R$&nbsp;{formatUnitPrice(op.valor_unitario)}</td>
                <td className="px-4 py-2 text-right type-num-table">{formatBRL(op.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {ops.data && <p className="type-caption text-muted-foreground">{ops.data.length} operação(ões)</p>}
    </div>
  );
}

export function OperationsBlock() {
  const [open, setOpen] = useState(false);
  return (
    <section aria-labelledby="operacoes" className="space-y-3">
      <h2 id="operacoes" className="type-section-title">
        <button type="button" aria-expanded={open} className="inline-flex items-center gap-1" onClick={() => setOpen((v) => !v)}>
          <ChevronRightIcon aria-hidden className={cn("size-4 transition-transform", open && "rotate-90")} />
          Operações
        </button>
      </h2>
      {open && <Operations />}
    </section>
  );
}
