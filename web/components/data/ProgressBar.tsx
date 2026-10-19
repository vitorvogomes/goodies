// Barra de progresso (Story 8.7 — DESIGN › progress-bar, EXPERIENCE › Barra de progresso): três
// trechos sobre o planejado — realizado em ativo (sólido), a caminho (hachurado) e pendente (vazio)
// —, trilho com contorno `input`, legenda com os mesmos rótulos e os números escritos ao lado. As
// larguras chegam prontas da API (% do planejado).
import { cn } from "@/lib/utils";

const HATCH = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-positive) 0 2px, transparent 2px 6px)",
};

export function ProgressBar({
  label,
  solid,
  hatched = 0,
  legend,
  className,
}: {
  label: string;
  solid: number; // % em ativo
  hatched?: number; // % a caminho
  legend?: { realizado: string; aCaminho?: string; pendente: string };
  className?: string;
}) {
  return (
    <div className={cn("space-y-1", className)}>
      <div
        role="img"
        aria-label={label}
        className="flex h-2 w-full overflow-hidden rounded-full border border-input bg-muted"
      >
        <span className="h-full bg-positive" style={{ width: `${solid}%` }} />
        {hatched > 0 && <span className="h-full border-l border-card" style={{ width: `${hatched}%`, ...HATCH }} />}
      </div>
      {legend && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 type-caption text-muted-foreground">
          <li className="inline-flex items-center gap-1.5">
            <span aria-hidden className="size-2.5 rounded-sm bg-positive" />
            Realizado em ativo <span className="type-num-table text-foreground">{legend.realizado}</span>
          </li>
          {legend.aCaminho && (
            <li className="inline-flex items-center gap-1.5">
              <span aria-hidden className="size-2.5 rounded-sm border border-input" style={HATCH} />
              <span
                className="underline decoration-dotted underline-offset-4"
                title="Do que saiu da conta neste mês, o que ainda não virou ativo. O caixa total da corretora (Conciliação) inclui também proventos e sobras de meses anteriores."
              >
                Na corretora, não aplicado
              </span>{" "}
              <span className="type-num-table text-foreground">{legend.aCaminho}</span>
            </li>
          )}
          <li className="inline-flex items-center gap-1.5">
            <span aria-hidden className="size-2.5 rounded-sm border border-input bg-muted" />
            Pendente <span className="type-num-table text-foreground">{legend.pendente}</span>
          </li>
        </ul>
      )}
    </div>
  );
}
