"use client";

// Saldo em caixa (v2.2 — F2): o saldo das contas no último extrato, com a conferência ao centavo
// ("conferido" / "divergente"). Era a coluna Saldo do bloco Fontes, no fim do Painel; agora abre a
// página. Os números vêm da API (Fontes do Painel).
import Link from "next/link";

import { StatusBadge } from "@/components/data/StatusBadge";
import { KpiSkeleton } from "@/components/overview/KpiCard";
import { formatBRL, formatDate } from "@/lib/format";
import { useOverviewSources } from "@/lib/overview";

export function CashCard({ periodo }: { periodo: string }) {
  const fontes = useOverviewSources();
  if (fontes.isLoading) return <KpiSkeleton />;
  const accounts = (fontes.data ?? []).filter((s) => s.balance != null);
  const [main, ...others] = accounts;
  return (
    <section
      aria-labelledby="saldo-caixa"
      className="space-y-2 rounded-lg border border-border bg-card p-card-padding shadow-card"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="saldo-caixa" className="type-label text-muted-foreground">
          Saldo em caixa
        </h2>
        <Link href={`/caixa/transacoes?periodo=${periodo}`} className="type-body-sm text-positive underline">
          Transações
        </Link>
      </div>
      {fontes.isError || !main ? (
        <p className="type-body text-muted-foreground">
          {fontes.isError ? "Não foi possível carregar o saldo." : "Importe um extrato para ver o saldo."}
        </p>
      ) : (
        <>
          <Account s={main} big />
          {others.map((s) => (
            <Account key={s.key} s={s} />
          ))}
        </>
      )}
    </section>
  );
}

function Account({ s, big = false }: { s: NonNullable<ReturnType<typeof useOverviewSources>["data"]>[number]; big?: boolean }) {
  return (
    <div className={big ? "space-y-1" : "flex flex-wrap items-baseline justify-between gap-2 border-t border-border pt-2"}>
      {big ? (
        <>
          <p className="type-num-display whitespace-nowrap">{formatBRL(s.balance ?? 0)}</p>
          <div className="flex flex-wrap items-center gap-2 type-body-sm text-muted-foreground">
            <span>{s.label}</span>
            <Check s={s} />
          </div>
        </>
      ) : (
        <>
          <span className="type-body-sm text-muted-foreground">{s.label}</span>
          <span className="flex items-center gap-2">
            <span className="type-num-body">{formatBRL(s.balance ?? 0)}</span>
            <Check s={s} />
          </span>
        </>
      )}
    </div>
  );
}

function Check({ s }: { s: NonNullable<ReturnType<typeof useOverviewSources>["data"]>[number] }) {
  if (s.balance_status === "conferido" && s.balance_as_of) {
    return (
      <StatusBadge tooltip={`O saldo do extrato bate ao centavo com as transações até ${formatDate(s.balance_as_of)}.`}>
        conferido · {formatDate(s.balance_as_of)}
      </StatusBadge>
    );
  }
  if (s.balance_status === "divergente" && s.balance_difference !== null) {
    return (
      <StatusBadge
        tone="divergence"
        tooltip={`O saldo do extrato de ${s.balance_as_of ? formatDate(s.balance_as_of) : "—"} não fecha com as transações.`}
      >
        divergente · {formatBRL(Math.abs(s.balance_difference))}
      </StatusBadge>
    );
  }
  return s.balance_as_of ? <span className="type-caption">extrato de {formatDate(s.balance_as_of)}</span> : null;
}
