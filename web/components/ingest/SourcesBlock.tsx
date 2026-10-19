// Bloco Fontes (DESIGN.md › sources-block, Stories 3.9 e 3.13): uma linha por fonte de arquivo com
// tipo e "até dd/mm/aaaa" derivado só dos lotes aplicados/legado; fonte atrasada (FR-3) ganha ponto
// de aviso. A conta PF mostra o saldo da conta no extrato e "conferido" ou "divergente · R$ x"; o
// MEI não confere.
import { StatusBadge } from "@/components/data/StatusBadge";
import { formatBRL, formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SourceRow } from "@/types/ingest";

export function SourcesBlock({
  sources,
  loading,
  onOpenSource,
}: {
  sources: (SourceRow & { opens_hub?: boolean })[];
  loading?: boolean;
  /** Fonte de arquivo clicável (Painel): abre o Hub de import. */
  onOpenSource?: (key: string) => void;
}) {
  return (
    <table className="w-full type-body-sm">
      <caption className="sr-only">Fontes de arquivo</caption>
      <thead className="bg-muted">
        <tr>
          <th scope="col" className="type-label px-4 py-1.5 text-left font-medium">Fonte</th>
          <th scope="col" className="type-label px-4 py-1.5 text-left font-medium">Tipo</th>
          <th scope="col" className="type-label px-4 py-1.5 text-right font-medium">Atualizado até</th>
          <th scope="col" className="type-label px-4 py-1.5 text-left font-medium">Saldo</th>
        </tr>
      </thead>
      <tbody>
        {loading && (
          <tr>
            <td colSpan={4} className="px-4 py-2">
              <div className="h-4 animate-pulse rounded bg-muted" />
            </td>
          </tr>
        )}
        {sources.map((s) => (
          <tr key={s.key} className="border-t border-border">
            <td className="px-4 py-1.5">
              {onOpenSource && s.opens_hub ? (
                <button type="button" className="text-left underline decoration-border underline-offset-2 hover:decoration-foreground" onClick={() => onOpenSource(s.key)}>
                  {s.label}
                </button>
              ) : (
                s.label
              )}
            </td>
            <td className="px-4 py-1.5 text-muted-foreground">{s.kind}</td>
            <td className="px-4 py-1.5 text-right whitespace-nowrap">
              {s.stale && (
                <span
                  aria-label="fonte desatualizada"
                  className="mr-1.5 inline-block size-2 rounded-full bg-warning-dot ring-4 ring-warning-tint"
                />
              )}
              <span className={cn("type-num-table", !s.updated_until && "text-muted-foreground")}>
                {s.updated_until ? `até ${formatDate(s.updated_until)}` : "nunca importado"}
              </span>
            </td>
            <td className="px-4 py-1.5 whitespace-nowrap">
              {s.balance != null && (
                <span className="mr-2 type-num-table" aria-label={`Saldo da conta: ${formatBRL(s.balance)}`}>
                  {formatBRL(s.balance)}
                </span>
              )}
              {s.balance_status === "conferido" && s.balance_as_of && (
                <StatusBadge tooltip={`Saldo do extrato bate ao centavo até ${formatDate(s.balance_as_of)}.`}>
                  conferido · {formatDate(s.balance_as_of)}
                </StatusBadge>
              )}
              {s.balance_status === "divergente" && s.balance_difference !== null && (
                <StatusBadge
                  tone="divergence"
                  tooltip={`O saldo do extrato de ${s.balance_as_of ? formatDate(s.balance_as_of) : "—"} não fecha com as transações.`}
                >
                  divergente · {formatBRL(Math.abs(s.balance_difference))}
                </StatusBadge>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
