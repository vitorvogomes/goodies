"use client";

// Aportes fixos do mês (Ajustes › Metas, pedido de 18/10/2026): o valor que um objetivo ou um ativo
// recebe todo mês — a integralização da Flash, a caixinha de um objetivo. Na Distribuição do aporte
// viram travas padrão (a trava do próprio mês vence). Salvar vale a partir deste mês; excluir fecha a
// vigência no mês anterior. Lista e opções vêm da API.
import { useState } from "react";
import { toast } from "sonner";

import { RowActions } from "@/components/data/RowActions";
import { SAVE_FAILED } from "@/components/forms/SideForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatBRL, formatMonth, normalizeMoneyInput } from "@/lib/format";
import { useDeleteFixedContribution, useFixedContributions, useSaveFixedContribution } from "@/lib/planning";

const SELECT = "h-9 w-full rounded-md border border-input bg-background px-2 type-body-sm text-foreground";

export function FixedContributions() {
  const fixed = useFixedContributions();
  const save = useSaveFixedContribution();
  const remove = useDeleteFixedContribution();
  const [key, setKey] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (fixed.isError && !fixed.data) return <p className="type-body text-negative">Não foi possível carregar os aportes fixos.</p>;
  const data = fixed.data;
  const groups = [...new Set((data?.options ?? []).map((o) => o.group))];

  function submit() {
    const money = normalizeMoneyInput(amount);
    if (!key) return setError("Escolha o objetivo ou o ativo.");
    if (!money || Number(money) <= 0) return setError("Informe um valor maior que zero (ex.: 1.000,00).");
    setError(null);
    save.mutate(
      { key, amount: money },
      {
        onSuccess: () => {
          toast("Aporte fixo salvo.");
          setKey("");
          setAmount("");
        },
        onError: () => setError(SAVE_FAILED),
      },
    );
  }

  return (
    <section aria-labelledby="aportes-fixos" className="space-y-3">
      <div>
        <h2 id="aportes-fixos" className="type-section-title">
          Aportes fixos do mês
        </h2>
        <p className="type-caption text-muted-foreground">
          O que entra todo mês no mesmo valor. Na distribuição do aporte, a linha já vem travada nele.
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card shadow-card">
        {data && data.items.length > 0 ? (
          <ul className="divide-y divide-border type-body-sm">
            {data.items.map((i) => (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2">
                <span>
                  {i.label}
                  <span className="block type-caption text-muted-foreground">desde {formatMonth(i.valid_from.slice(0, 7))}</span>
                </span>
                <span className="flex items-center gap-3">
                  <span className="type-num-table">{formatBRL(i.amount)}/mês</span>
                  <RowActions
                    subject={i.label}
                    onEdit={() => {
                      setKey(i.key);
                      setAmount(i.amount.toFixed(2).replace(".", ","));
                    }}
                    onDelete={() =>
                      remove.mutate(i.key, {
                        onSuccess: () => toast("Aporte fixo excluído."),
                        onError: () => toast(SAVE_FAILED),
                      })
                    }
                  />
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-4 py-3 type-body-sm text-muted-foreground">
            {fixed.isLoading ? "Carregando…" : "Nenhum aporte fixo."}
          </p>
        )}
        <form
          className="flex flex-wrap items-end gap-2 border-t border-border px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <label className="min-w-56 flex-1 space-y-1 type-caption text-muted-foreground">
            Objetivo ou ativo
            <select value={key} onChange={(e) => setKey(e.target.value)} className={SELECT}>
              <option value="">Escolha…</option>
              {groups.map((g) => (
                <optgroup key={g} label={g}>
                  {(data?.options ?? [])
                    .filter((o) => o.group === g)
                    .map((o) => (
                      <option key={o.key} value={o.key}>
                        {o.label}
                      </option>
                    ))}
                </optgroup>
              ))}
            </select>
          </label>
          <label className="w-36 space-y-1 type-caption text-muted-foreground">
            Valor por mês (R$)
            <Input
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0,00"
              className="type-num-body text-right"
              aria-invalid={Boolean(error)}
            />
          </label>
          <Button type="submit" disabled={save.isPending}>
            Salvar
          </Button>
          {error && (
            <p role="alert" className="w-full type-caption text-negative">
              {error}
            </p>
          )}
        </form>
      </div>
    </section>
  );
}
