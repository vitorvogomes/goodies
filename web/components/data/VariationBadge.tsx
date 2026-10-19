// Selo de variação (Story 9.1 — DESIGN › variation-badge, UX-DR15): seta + sinal + valor, em
// tint; zero = "0,00%" neutro. A cor diz se a variação é boa: gasto que sobe é ruim (`good="down"`).
// O valor chega pronto da API (% sobre a referência, ou p.p. para taxas).
import { TrendArrow } from "@/components/data/TrendArrow";
import { cn } from "@/lib/utils";

export function VariationBadge({
  value,
  unit = "%",
  good = "up",
}: {
  value: number | null;
  unit?: "%" | "p.p.";
  good?: "up" | "down";
}) {
  if (value === null) return <span className="text-muted-foreground">—</span>;
  const text = Math.abs(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (value === 0) {
    return (
      <span className="type-tag inline-flex min-w-[66px] justify-center rounded-sm bg-secondary px-2 text-secondary-foreground">
        0,00{unit === "%" ? "%" : " p.p."}
      </span>
    );
  }
  const up = value > 0;
  const better = up === (good === "up");
  return (
    <span
      className={cn(
        "type-tag inline-flex min-w-[66px] items-center justify-center gap-1 rounded-sm px-2 whitespace-nowrap",
        better ? "bg-positive-tint text-positive" : "bg-negative-tint text-negative",
      )}
    >
      <TrendArrow up={up} className="mr-0" />
      {up ? "+" : "−"}
      {text}
      {unit === "%" ? "%" : " p.p."}
    </span>
  );
}
