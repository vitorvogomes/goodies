"use client";

// Visão geral do Portfolio (m2): headline de XIRR + atalhos para as telas.
import Link from "next/link";

import { Card } from "@/components/ui";
import { formatBRL, formatRate } from "@/lib/format";
import { useAllocation, useXIRR } from "@/lib/portfolio";

const LINKS = [
  { href: "/portfolio/positions", label: "Posições", desc: "Carteira atual e resultado" },
  { href: "/portfolio/history", label: "Histórico", desc: "Operações registradas" },
  { href: "/portfolio/allocation", label: "Alocação", desc: "Atual vs. meta" },
  { href: "/portfolio/rebalancing", label: "Rebalanceamento", desc: "Sugestão de aporte" },
];

export default function PortfolioPage() {
  const xirr = useXIRR();
  const allocation = useAllocation();

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-2xl font-semibold text-foreground">Portfolio</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card>
          <p className="text-sm text-foreground/50">XIRR consolidado (a.a.)</p>
          <p className="mt-1 text-3xl font-semibold tabular-nums text-gain">
            {xirr.isLoading ? "…" : formatRate(xirr.data?.consolidated ?? null)}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-foreground/50">Patrimônio (valorado)</p>
          <p className="mt-1 text-3xl font-semibold tabular-nums text-foreground">
            {allocation.isLoading ? "…" : formatBRL(allocation.data?.total ?? 0)}
          </p>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href}>
            <Card className="transition hover:border-accent/50">
              <p className="font-medium text-foreground/90">{l.label}</p>
              <p className="mt-0.5 text-sm text-foreground/50">{l.desc}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
