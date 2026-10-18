"use client";

// Aporte planejado do mês (Story 8.4 — FR-28): o campo (Enter grava, Esc reverte) e, logo abaixo,
// "Disponível para consumo depois do aporte" recalculado pela API. Sem valor: "Defina o aporte
// planejado de {mês} para ver a distribuição." Mês fechado: só leitura até reabrir.
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { formatBRL, formatMonth, normalizeMoneyInput } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { MonthBudget } from "@/types/planning";

export const SAVE_FAILED = "Não foi possível salvar. Nada foi perdido. Tentar de novo.";

export function AportePlanejado({
  budget,
  periodo,
  saving,
  autoFocus,
  onCommit,
}: {
  budget: MonthBudget;
  periodo: string;
  saving: boolean;
  autoFocus: boolean;
  onCommit: (valor: string | null, onError: () => void) => void;
}) {
  // O pai remonta o campo (key) quando o valor gravado muda; a mutação fica no pai (a resposta
  // chegaria a um campo já remontado).
  const shown = budget.aporte_definido ? budget.aporte_planejado.toFixed(2).replace(".", ",") : "";
  const [value, setValue] = useState(shown);
  const [error, setError] = useState<string | null>(null);
  const disponivel = budget.disponivel.value;

  function commit() {
    const raw = value.trim();
    const normalized = raw === "" ? null : normalizeMoneyInput(raw);
    if (raw !== "" && (normalized === null || Number(normalized) < 0)) {
      setError("Informe um valor (ex.: 4.500,00) ou deixe vazio para não definir.");
      return;
    }
    setError(null);
    onCommit(normalized, () => setError(SAVE_FAILED));
  }

  return (
    <section aria-labelledby="aporte-titulo" className="space-y-2 rounded-lg border border-border bg-card p-card-padding">
      <h2 id="aporte-titulo" className="type-section-title">
        Aporte planejado de {formatMonth(periodo)}
      </h2>
      {budget.closed ? (
        <p className="type-num-lg">{budget.aporte_definido ? formatBRL(budget.aporte_planejado) : "não definido"}</p>
      ) : (
        <Input
          id="aporte-planejado"
          aria-label={`Aporte planejado de ${formatMonth(periodo)}`}
          aria-describedby="aporte-legenda"
          inputMode="decimal"
          placeholder="0,00"
          value={value}
          disabled={saving}
          autoFocus={autoFocus}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setValue(shown);
              setError(null);
            }
          }}
          aria-invalid={Boolean(error)}
          className="h-11 w-56 type-num-lg"
        />
      )}
      <p id="aporte-legenda" className="type-caption text-muted-foreground">
        {budget.closed ? "mês fechado: só leitura até reabrir" : "Enter grava, Esc reverte"}
      </p>
      {error && (
        <p role="alert" className="type-caption text-negative">
          {error}
        </p>
      )}
      <p role="status" aria-live="polite" className="flex justify-between gap-4 border-t border-border pt-2 type-body-sm">
        <span>Disponível para consumo depois do aporte</span>
        <span className={cn("type-num-body", disponivel !== null && disponivel < 0 && "text-negative")}>
          {disponivel !== null ? formatBRL(disponivel) : "—"}
        </span>
      </p>
      {!budget.aporte_definido && !budget.closed && (
        <p className="type-body-sm text-muted-foreground">
          Defina o aporte planejado de {formatMonth(periodo)} para ver a distribuição.
        </p>
      )}
    </section>
  );
}
