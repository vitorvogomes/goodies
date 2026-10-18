"use client";

// Faixa "Criar regra?" (Story 3.11 — FR-10, UX-DR32): sob a linha cuja categoria veio de regra ou
// sugestão e foi trocada. Criar regra grava (com o lote, se veio da Revisão) e aplica às afetadas que
// não são manuais; Ajustar condição mostra a prévia ao vivo; Agora não fecha. Não bloqueia o resto.
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateRule, useRulePreview, useRuleProposal } from "@/lib/ledger";
import { useDebounced } from "@/lib/use-debounced";

export function RuleProposalStrip({
  transactionId,
  categoryId,
  lote,
  onClose,
}: {
  transactionId: string;
  categoryId: string;
  lote?: string | null;
  onClose: () => void;
}) {
  const proposal = useRuleProposal(transactionId, categoryId);
  const create = useCreateRule();
  const [adjusting, setAdjusting] = useState(false);
  const [pattern, setPattern] = useState<string | null>(null);
  const current = pattern ?? proposal.data?.pattern ?? "";
  const preview = useRulePreview(
    useDebounced(adjusting ? current : ""),
    proposal.data?.direction ?? "saida",
  );

  if (!proposal.data || !proposal.data.pattern) return null;
  const p = proposal.data;

  function save() {
    create.mutate(
      { pattern: current, direction: p.direction, category_id: p.category_id, lote },
      {
        onSuccess: ({ applied }) => {
          toast(
            applied === 1
              ? "Regra criada. 1 transação recategorizada."
              : `Regra criada. ${applied} transações recategorizadas.`,
          );
          onClose();
        },
        onError: () => toast("Não foi possível criar a regra. Nada foi perdido."),
      },
    );
  }

  return (
    <div role="region" aria-label="Proposta de regra" className="space-y-2 rounded-md bg-muted px-3 py-2 type-body-sm">
      <p>
        Criar regra? Descrição contém “{current}” → {p.category_label}.{" "}
        {adjusting
          ? `${preview.data?.total ?? 0} ${preview.data?.total === 1 ? "transação bate" : "transações batem"} com a condição.`
          : `Afeta ${p.affected} ${p.affected === 1 ? "outra transação" : "outras transações"}.`}
      </p>
      {adjusting && (
        <Input
          aria-label="Descrição contém"
          value={current}
          onChange={(e) => setPattern(e.target.value)}
          className="h-8 max-w-80"
        />
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={!current.trim() || create.isPending} onClick={save}>
          Criar regra
        </Button>
        {!adjusting && (
          <Button size="sm" variant="secondary" onClick={() => setAdjusting(true)}>
            Ajustar condição
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={onClose}>
          Agora não
        </Button>
      </div>
    </div>
  );
}
