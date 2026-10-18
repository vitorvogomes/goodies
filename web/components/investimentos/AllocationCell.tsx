"use client";

// Alocação × meta ± banda numa célula só (pedido de 18/10/2026: desvio e bandas mais didáticos): a
// régua mostra a faixa aceita (meta ± banda) e onde a alocação está; o texto diz quanto falta ou
// sobra em p.p. e se está dentro da banda. Números da API (Story 8.3); a régua só posiciona.
import { formatPercent, formatPP } from "@/lib/format";
import { cn } from "@/lib/utils";

export function AllocationCell({
  alocacao,
  meta,
  banda,
  desvio,
  fora,
  compact = false,
}: {
  alocacao: number | null;
  meta: number | null;
  banda: number | null;
  desvio: number | null;
  fora: boolean;
  compact?: boolean; // linha de ativo: % na classe e a meta do ativo, sem régua
}) {
  if (alocacao == null) return <span className="text-muted-foreground">—</span>;
  if (meta == null || compact) {
    return (
      <span className="inline-flex flex-col items-end">
        <span>{formatPercent(alocacao)}</span>
        {meta != null && (
          <span className="type-caption text-muted-foreground">
            meta {formatPercent(meta)}
            {desvio != null && desvio !== 0 && ` · ${formatPP(desvio)}`}
          </span>
        )}
      </span>
    );
  }
  const band = banda ?? 0;
  const scale = Math.max(alocacao, meta + band, 1) * 1.15;
  const at = (v: number) => `${Math.min(Math.max(v / scale, 0), 1) * 100}%`;
  const status = fora
    ? `${formatPP(desvio ?? 0)} · ${(desvio ?? 0) > 0 ? "acima" : "abaixo"} da banda`
    : `${formatPP(desvio ?? 0)} · dentro da banda`;
  return (
    <span className="inline-flex min-w-36 flex-col items-end gap-1 whitespace-nowrap">
      <span>
        {formatPercent(alocacao)}{" "}
        <span className="type-caption font-normal text-muted-foreground">
          · meta {formatPercent(meta)}
          {band > 0 && ` ± ${String(band).replace(".", ",")}`}
        </span>
      </span>
      <span aria-hidden className="relative block h-1.5 w-28 rounded-full bg-muted">
        <span
          className="absolute inset-y-0 rounded-full bg-positive-tint"
          style={{ left: at(meta - band), width: `calc(${at(meta + band)} - ${at(meta - band)})` }}
        />
        <span className="absolute inset-y-[-2px] w-px bg-muted-foreground" style={{ left: at(meta) }} />
        <span
          className={cn(
            "absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card",
            fora ? "bg-warning" : "bg-foreground",
          )}
          style={{ left: at(alocacao) }}
        />
      </span>
      <span className={cn("type-caption font-normal", fora ? "text-warning" : "text-muted-foreground")}>{status}</span>
    </span>
  );
}
