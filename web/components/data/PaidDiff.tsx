// Pago × previsto de um custo fixo (v2.2): só indicativo — "economia R$ 23" quando saiu menos que o
// cadastrado, "R$ 40 a mais" quando saiu mais. Igual ou sem valor pago (marcado à mão): nada.
import { formatBRL } from "@/lib/format";
import { cn } from "@/lib/utils";

export function PaidDiff({ difference, className }: { difference: number | null; className?: string }) {
  if (difference === null || difference === 0) return null;
  const saved = difference > 0;
  return (
    <span
      className={cn(
        "type-tag inline-flex items-center rounded-full px-2 whitespace-nowrap",
        saved ? "bg-positive-tint text-positive" : "bg-warning-tint text-warning",
        className,
      )}
    >
      {saved ? `economia ${formatBRL(difference)}` : `${formatBRL(-difference)} a mais`}
    </span>
  );
}

/** Linha de total: "R$ 23 de economia no que já foi pago" / "R$ 40 a mais no que já foi pago". */
export function paidDiffText(total: number): string | null {
  if (total === 0) return null;
  return total > 0
    ? `${formatBRL(total)} de economia no que já foi pago`
    : `${formatBRL(-total)} a mais no que já foi pago`;
}
