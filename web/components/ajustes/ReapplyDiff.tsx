// Prévia da reaplicação de regras (Story 2.10): antes × depois por transação, com o aviso das
// categorias manuais preservadas e das transações em meses fechados (o congelado não muda — 5.6).
import { ArrowRightIcon } from "lucide-react";

import { formatDate, formatSignedBRL } from "@/lib/format";
import type { ReapplyPreview } from "@/types/ledger";

export function ReapplyDiff({ preview }: { preview: ReapplyPreview }) {
  const { changes, manual_unchanged, closed_months } = preview;
  return (
    <div className="space-y-2">
      <p className="type-body-sm text-muted-foreground" role="status">
        {changes.length === 0
          ? "Nada a mudar: as regras já batem com o histórico desse período."
          : `${changes.length} ${changes.length === 1 ? "transação muda" : "transações mudam"} de categoria.`}{" "}
        {manual_unchanged} {manual_unchanged === 1 ? "categoria manual não será alterada" : "categorias manuais não serão alteradas"}.
        {closed_months > 0 &&
          ` ${closed_months} ${closed_months === 1 ? "transação em mês fechado" : "transações em meses fechados"}: o resumo congelado não muda.`}
      </p>
      {changes.length > 0 && (
        <div className="max-h-96 overflow-y-auto rounded-lg border border-border bg-card shadow-card" tabIndex={0} role="region" aria-label="Antes e depois">
          <table className="w-full type-body-sm">
            <caption className="sr-only">Antes e depois da reaplicação</caption>
            <thead className="sticky top-0 bg-muted">
              <tr>
                <th scope="col" className="type-label px-4 py-2 text-left font-medium">Data</th>
                <th scope="col" className="type-label px-4 py-2 text-left font-medium">Descrição</th>
                <th scope="col" className="type-label px-4 py-2 text-right font-medium">Valor</th>
                <th scope="col" className="type-label px-4 py-2 text-left font-medium">Antes → depois</th>
              </tr>
            </thead>
            <tbody>
              {changes.map((c) => (
                <tr key={c.transaction_id} className="border-t border-border">
                  <td className="px-4 py-2 whitespace-nowrap">{formatDate(c.date)}</td>
                  <td className="max-w-64 truncate px-4 py-2" title={c.description ?? undefined}>
                    {c.description ?? "—"}
                  </td>
                  <td className="px-4 py-2 text-right whitespace-nowrap type-num-table">{formatSignedBRL(c.amount)}</td>
                  <td className="px-4 py-2">
                    <span className="text-muted-foreground line-through">{c.before}</span>
                    <ArrowRightIcon aria-label="passa para" className="mx-1 inline size-3" />
                    <span className="font-semibold">{c.after}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
