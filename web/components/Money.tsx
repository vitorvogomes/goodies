// Célula de dinheiro: BRL como principal, USD em mute logo abaixo. "—" sem preço.
// `usdPartial` marca com "*" um total USD que subestima (algum item sem preço USD).
// Reuso entre Carteiras, Posições (bloco cripto) e Reconciliação — fonte única do par
// BRL/USD para que todo lugar que mostra valor de cripto exiba real e dólar.
import { formatBRL, formatUSD } from "@/lib/format";

export function Money({
  brl,
  usd,
  usdPartial = false,
}: {
  brl: number | null;
  usd: number | null;
  usdPartial?: boolean;
}) {
  if (brl == null) return <span className="text-foreground/40">—</span>;
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="tabular-nums text-foreground/80">{formatBRL(brl)}</span>
      {usd != null && (
        <span className="tabular-nums text-[11px] text-foreground/40">
          {formatUSD(usd)}
          {usdPartial && "*"}
        </span>
      )}
    </div>
  );
}
