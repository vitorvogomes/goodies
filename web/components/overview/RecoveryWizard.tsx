"use client";

// Assistente de recuperação (Story 5.8 — UX-DR41, DESIGN › recovery-wizard): cartão no topo do
// Painel enquanto a trilha (do mês seguinte ao bloco retroativo até o mês anterior) tiver mês aberto.
// Meses em mono com o Selo de estado; sob o mês atual, os 4 passos (feito com check neutro, atual em
// 600, a fazer esmaecido) e um único botão primário no passo atual. Tudo vem da API (dos dados):
// pausar não perde nada. Os links levam o período do mês, e o Seletor acompanha.
import { CheckIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CloseDialog } from "@/components/closing/CloseDialog";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/button";
import { useRecovery } from "@/lib/closing";
import { formatMonth } from "@/lib/format";
import { cn } from "@/lib/utils";

export function RecoveryWizard() {
  const recovery = useRecovery();
  const [closing, setClosing] = useState<string | null>(null);
  const data = recovery.data;
  if (!data?.active || !data.current) return null;
  const periodo = data.current.slice(0, 7);
  const label = formatMonth(periodo);

  return (
    <section
      aria-labelledby="recuperacao"
      className="space-y-3 rounded-lg border border-border bg-card shadow-card p-card-padding"
    >
      <div className="space-y-0.5">
        <h2 id="recuperacao" className="type-section-title">
          Assistente de recuperação
        </h2>
        <p className="type-body-sm text-muted-foreground">{data.message}</p>
      </div>
      <ol className="flex flex-wrap gap-2" aria-label="Meses a recuperar">
        {data.months.map((m) => {
          const p = m.month.slice(0, 7);
          const current = p === periodo;
          return (
            <li key={m.month}>
              <Link
                href={`/visao-geral/painel?periodo=${p}`}
                aria-current={current ? "step" : undefined}
                className={cn(
                  "flex items-center gap-1.5 rounded-md border px-2 py-1 type-num-body focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  current ? "border-foreground" : "border-border",
                )}
              >
                {formatMonth(p)}
                <StatusBadge tone={m.status === "ajuste" ? "warning" : "neutral"}>{m.status}</StatusBadge>
              </Link>
            </li>
          );
        })}
      </ol>
      <ol className="grid gap-2 sm:grid-cols-4" aria-label={`Passos de ${label}`}>
        {data.steps.map((s) => (
          <li
            key={s.key}
            className="flex flex-col gap-1.5"
          >
            <span
              className={cn(
                "flex items-center gap-1.5 type-label",
                s.state === "a_fazer" ? "text-muted-foreground" : "text-foreground",
                s.state === "atual" && "font-semibold",
              )}
            >
              {s.state === "feito" && <CheckIcon aria-label="feito" className="size-4" />}
              {s.label}
              {s.detail && <span className="font-normal text-muted-foreground">· {s.detail}</span>}
            </span>
            {s.state === "atual" &&
              (s.key === "fechar" ? (
                <Button size="sm" className="w-fit" onClick={() => setClosing(periodo)}>
                  Fechar {label}
                </Button>
              ) : (
                <Button size="sm" className="w-fit" asChild>
                  <Link href={s.href ?? `/visao-geral/painel?periodo=${periodo}`}>
                    {s.label} {label}
                  </Link>
                </Button>
              ))}
          </li>
        ))}
      </ol>
      <CloseDialog periodo={closing} onClose={() => setClosing(null)} />
    </section>
  );
}
