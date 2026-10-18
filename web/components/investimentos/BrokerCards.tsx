"use client";

// Cartões de corretora (Story 7.7 — FR-25, UX-DR39): por corretora, saiu do Nubank, proventos,
// aplicado, caixa em corretora (no patrimônio) e a caminho (Selo + "importe o relatório B3 a partir
// de dd/mm/aaaa", fora do patrimônio), com o Carimbo de data do relatório. "Saldo que vejo na
// corretora" (valor + data) grava a conferência; calculado × informado, diferença > R$ 1,00 =
// Selo "divergente". Os números vêm da API.
import { useState } from "react";
import { toast } from "sonner";

import { DateStamp } from "@/components/data/DateStamp";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatBRL, formatDate, normalizeMoneyInput } from "@/lib/format";
import { currentDayBRT } from "@/lib/period";
import { useBrokerCheck, useBrokers } from "@/lib/positions";
import type { BrokerCard } from "@/types/positions";

function CheckForm({ card }: { card: BrokerCard }) {
  const save = useBrokerCheck();
  const [value, setValue] = useState("");
  const [day, setDay] = useState(currentDayBRT());
  const [error, setError] = useState<string | null>(null);
  function submit() {
    const money = normalizeMoneyInput(value);
    if (money === null || !/^\d{4}-\d{2}-\d{2}$/.test(day)) {
      setError("Informe o saldo (ex.: 1.234,56) e a data.");
      return;
    }
    if (day > currentDayBRT()) {
      setError("A data do saldo não pode ser depois de hoje.");
      return;
    }
    setError(null);
    save.mutate(
      { rail: card.rail, as_of: day, balance: money },
      {
        onSuccess: () => {
          toast("Saldo informado.");
          setValue("");
        },
        onError: () => setError("Não foi possível salvar. Nada foi perdido. Tentar de novo."),
      },
    );
  }
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <label className="space-y-1 type-caption text-muted-foreground">
        Saldo que vejo na corretora
        <Input
          inputMode="decimal"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="0,00"
          className="h-8 w-32 type-num-body text-right"
          aria-label={`Saldo que vejo na ${card.name}`}
        />
      </label>
      <label className="space-y-1 type-caption text-muted-foreground">
        em
        <Input
          type="date"
          value={day}
          max={currentDayBRT()}
          onChange={(e) => setDay(e.target.value)}
          className="h-8 w-40"
        />
      </label>
      <Button size="sm" variant="secondary" type="submit" disabled={save.isPending}>
        Informar
      </Button>
      {error && (
        <span role="alert" className="w-full type-caption text-negative">
          {error}
        </span>
      )}
    </form>
  );
}

function Row({ label, value, note }: { label: string; value: string; note?: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="text-muted-foreground">
        {label} {note}
      </dt>
      <dd className="type-num-table">{value}</dd>
    </div>
  );
}

export function BrokerCards() {
  const brokers = useBrokers();
  if (brokers.isError) return <p className="type-body text-negative">Não foi possível carregar as corretoras.</p>;
  if (!brokers.data) return <div className="h-48 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />;
  return (
    <div className="grid gap-card-gap md:grid-cols-2">
      {brokers.data.map((b) => (
        <section key={b.rail} aria-labelledby={`corretora-${b.rail}`} className="space-y-2 rounded-lg border border-border bg-card shadow-card p-card-padding">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 id={`corretora-${b.rail}`} className="type-section-title">
              {b.name}
            </h3>
            <DateStamp asOf={b.covered_until} source="relatório" />
          </div>
          <dl className="space-y-1 type-body-sm">
            <Row label="Saiu do Nubank" value={formatBRL(b.saiu)} />
            <Row label="Proventos" value={formatBRL(b.proventos)} />
            <Row label="Aplicado" value={formatBRL(b.aplicado)} />
            <Row label="Caixa em corretora" value={formatBRL(b.caixa)} note={<span className="type-caption">(no patrimônio)</span>} />
            <Row
              label="A caminho"
              value={formatBRL(b.a_caminho)}
              note={
                b.a_caminho > 0 ? (
                  <span className="inline-flex flex-wrap items-center gap-1">
                    <StatusBadge tone="warning">a caminho</StatusBadge>
                    {b.import_from && (
                      <span className="type-caption">importe a partir de {formatDate(b.import_from)}</span>
                    )}
                  </span>
                ) : undefined
              }
            />
            {b.informed !== null && b.informed_at && (
              <Row
                label={`Informado em ${formatDate(b.informed_at)}`}
                value={formatBRL(b.informed)}
                note={
                  b.divergent ? (
                    <StatusBadge
                      tone="divergence"
                      tooltip={`calculado em ${formatDate(b.informed_at)}: ${formatBRL(b.caixa_at_check ?? b.caixa)} — diferença acima de R$ 1,00`}
                    >
                      divergente
                    </StatusBadge>
                  ) : (
                    <StatusBadge>conferido</StatusBadge>
                  )
                }
              />
            )}
          </dl>
          <CheckForm card={b} />
        </section>
      ))}
    </div>
  );
}
