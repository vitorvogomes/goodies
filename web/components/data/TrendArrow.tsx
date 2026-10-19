// Seta de sentido (▲/▼) discreta: menor que o número que acompanha.
// Só reforça o sinal, que o texto já diz ("+"/"−").
import { cn } from "@/lib/utils";

export function TrendArrow({ up, className }: { up: boolean; className?: string }) {
  return (
    <span aria-hidden className={cn("mr-1 inline-block align-middle text-[0.55em] leading-none", className)}>
      {up ? "▲" : "▼"}
    </span>
  );
}
