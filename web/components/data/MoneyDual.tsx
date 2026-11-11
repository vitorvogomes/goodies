// Dinheiro em R$ e US$ (v2.2): cripto mostra os dois em todo lugar — R$ na linha principal, US$
// logo abaixo no mesmo tamanho de número de tabela, mais apagado. Sem US$ (sem cotação), só o R$.
import type { ReactNode } from "react";

import { formatUSD } from "@/lib/format";
import { cn } from "@/lib/utils";

export function MoneyDual({
  brl,
  usd,
  className,
  usdClassName,
}: {
  /** O R$ já formatado (ou um nó, ex.: valor com sinal e cor). */
  brl: ReactNode;
  usd: number | null | undefined;
  className?: string;
  usdClassName?: string;
}) {
  if (usd == null) return <>{brl}</>;
  return (
    <span className={cn("inline-flex flex-col items-end", className)}>
      <span>{brl}</span>
      <span className={cn("type-num-table font-normal text-muted-foreground", usdClassName)}>
        {formatUSD(usd)}
      </span>
    </span>
  );
}
