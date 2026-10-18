// Bloco Fontes (DESIGN.md › sources-block, Story 3.9): uma linha por fonte de arquivo com tipo e
// "até dd/mm/aaaa" derivado só dos lotes aplicados/legado; fonte atrasada (FR-3) ganha ponto de aviso.
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SourceRow } from "@/types/ingest";

export function SourcesBlock({ sources, loading }: { sources: SourceRow[]; loading?: boolean }) {
  return (
    <table className="w-full type-body-sm">
      <caption className="sr-only">Fontes de arquivo</caption>
      <thead className="bg-muted">
        <tr>
          <th scope="col" className="type-label px-4 py-1.5 text-left font-medium">Fonte</th>
          <th scope="col" className="type-label px-4 py-1.5 text-left font-medium">Tipo</th>
          <th scope="col" className="type-label px-4 py-1.5 text-right font-medium">Atualizado até</th>
        </tr>
      </thead>
      <tbody>
        {loading && (
          <tr>
            <td colSpan={3} className="px-4 py-2">
              <div className="h-4 animate-pulse rounded bg-muted" />
            </td>
          </tr>
        )}
        {sources.map((s) => (
          <tr key={s.key} className="border-t border-border">
            <td className="px-4 py-1.5">{s.label}</td>
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
          </tr>
        ))}
      </tbody>
    </table>
  );
}
