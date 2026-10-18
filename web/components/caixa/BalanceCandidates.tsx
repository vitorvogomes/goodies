"use client";

// Transações candidatas de uma divergência de saldo (Story 3.13 — UX-DR16): as do intervalo
// divergente da conta PF, da que tem valor mais perto da diferença para a mais longe. Abre pela
// ação "Ver transações" do aviso (`?conferencia=<início>_<fim>`).
import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { formatBRL, formatDate, formatSignedBRL } from "@/lib/format";
import { useBalanceCandidates } from "@/lib/ledger";
import type { BalanceCandidates as Candidates } from "@/types/ledger";

type Item = Candidates["items"][number];

const COLUMNS: DataColumn<Item>[] = [
  { id: "data", header: "Data", value: (i) => i.date, cell: (i) => formatDate(i.date) },
  {
    id: "descricao",
    header: "Descrição",
    value: (i) => i.description,
    cell: (i) => <span className="block max-w-96 truncate">{i.description ?? "—"}</span>,
  },
  { id: "valor", header: "Valor", numeric: true, value: (i) => i.amount, cell: (i) => formatSignedBRL(i.amount) },
  { id: "categoria", header: "Categoria", value: (i) => i.category_label },
];

export function BalanceCandidates({
  range,
  onClose,
}: {
  range: { start: string; end: string };
  onClose: () => void;
}) {
  const candidates = useBalanceCandidates(range);
  if (candidates.isError) {
    return <p className="type-body-sm text-negative">Não foi possível carregar a conferência.</p>;
  }
  if (!candidates.data) return null;
  const { difference, items } = candidates.data;
  return (
    <section aria-labelledby="conferencia" className="space-y-2 rounded-lg border border-negative bg-negative-tint/40 p-card-padding">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="conferencia" className="type-section-title">
            Saldo divergente em {formatBRL(Math.abs(difference))} na conta PF
          </h2>
          <p className="type-body-sm text-muted-foreground">
            Entre {formatDate(range.start)} e {formatDate(range.end)}. Transações candidatas, da mais
            perto da diferença para a mais longe.
          </p>
        </div>
        <button type="button" className="type-body-sm text-positive underline" onClick={onClose}>
          Fechar
        </button>
      </div>
      <DataTable
        tableId="conferencia-candidatas"
        caption="Transações candidatas da divergência"
        data={items}
        columns={COLUMNS}
        getRowId={(i) => i.id}
        empty="Nenhuma transação no intervalo: falta lançamento do extrato."
      />
    </section>
  );
}
