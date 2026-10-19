// Seta de sentido (▲/▼) discreta: menor que o número que acompanha (pedido de 18/10/2026 — as setas
// estavam do tamanho do valor). Só reforça o sinal, que o texto já diz ("+"/"−").
import { cn } from "@/lib/utils";

export function TrendArrow({ up, className }: { up: boolean; className?: string }) {
  return (
    <span aria-hidden className={cn("mr-1 inline-block align-middle text-[0.55em] leading-none", className)}>
      {up ? "▲" : "▼"}
    </span>
  );
}
