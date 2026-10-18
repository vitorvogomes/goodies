// Carimbo de data (DESIGN.md › date-stamp, Story 4.1): "até dd/mm/aaaa" da fonte do número, com a
// fonte no tooltip. Defasado (preço velho, API fora) → "preço de dd/mm/aaaa" + ponto de aviso.
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { formatDate } from "@/lib/format";

const SOURCE: Record<string, string> = {
  ledger: "extratos importados",
  portfolio: "posições, preços e carteiras",
};

export function DateStamp({
  asOf,
  source,
  stale = false,
}: {
  asOf: string | null;
  source?: string | null;
  stale?: boolean;
}) {
  if (!asOf) return null;
  const text = stale ? `preço de ${formatDate(asOf)}` : `até ${formatDate(asOf)}`;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="inline-flex items-center gap-1.5 type-caption text-muted-foreground">
          {stale && (
            <span aria-label="dado defasado" className="size-2 rounded-full bg-warning-dot ring-4 ring-warning-tint" />
          )}
          {text}
        </span>
      </TooltipTrigger>
      <TooltipContent>
        {source ? `Fonte: ${SOURCE[source] ?? source}.` : "Data dos dados."}
        {stale ? " Algum preço não pôde ser atualizado." : ""}
      </TooltipContent>
    </Tooltip>
  );
}
