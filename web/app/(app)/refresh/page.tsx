"use client";

// E4 — painel de frescor (Pilar 0). O app é local-on-demand: os dados se atualizam ao
// abrir (catch-up no AppShell) ou no botão "Atualizar tudo". Cada fonte só atualiza
// quando vencida (respeita os limites das APIs).
import { useState } from "react";

import { Badge, Button, Card } from "@/components/ui";
import { useFreshness, useRefreshAll, useRefreshRunning } from "@/lib/jobs";
import type { JobState } from "@/types/jobs";

const JOB_LABEL: Record<string, string> = {
  price_b3: "Preços B3 / Tesouro",
  price_crypto: "Preços cripto",
  wallet_scan: "Carteiras (scan)",
  benchmark: "Índices (CDI/IPCA)",
};

const STATE_BADGE: Record<JobState, { tone: "gain" | "warning" | "loss"; label: string }> = {
  fresh: { tone: "gain", label: "fresco" },
  stale: { tone: "warning", label: "vencido" },
  partial: { tone: "warning", label: "parcial" },
  error: { tone: "loss", label: "erro" },
};

function fmtAge(seconds: number | null): string {
  if (seconds == null) return "nunca rodou";
  const hours = seconds / 3600;
  if (hours < 1) return `há ${Math.max(1, Math.round(seconds / 60))} min`;
  if (hours < 48) return `há ${Math.round(hours)}h`;
  return `há ${Math.round(hours / 24)}d`;
}

export default function RefreshPage() {
  const running = useRefreshRunning(); // inclui o catch-up disparado pelo AppShell
  const fresh = useFreshness(running); // poll enquanto algo roda
  const refresh = useRefreshAll();
  const [notice, setNotice] = useState<string | null>(null);
  const jobs = fresh.data ?? [];

  function handleRefresh() {
    setNotice(null);
    refresh.mutate(true, {
      onSuccess: (res) => {
        if (res.status === "already_running") {
          setNotice("Já há uma atualização em andamento — aguarde concluir.");
        }
      },
      onError: () => setNotice("Falha ao atualizar. Tente novamente."),
    });
  }

  const busy = running || refresh.isPending;

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-mono text-2xl font-semibold text-foreground">Atualização</h1>
        <Button type="button" onClick={handleRefresh} disabled={busy}>
          {busy ? "Atualizando…" : "Atualizar tudo"}
        </Button>
      </div>
      <p className="text-sm text-foreground/50">
        O app é local: os dados se atualizam quando você abre ou clica acima. Cada fonte só
        atualiza quando vencida (respeitando os limites das APIs gratuitas).
      </p>
      {notice && (
        <p role="status" className="text-sm text-warning">
          {notice}
        </p>
      )}

      <Card>
        <ul className="space-y-3">
          {jobs.map((j) => {
            const badge = STATE_BADGE[j.status] ?? STATE_BADGE.stale;
            // wallet_scan: a idade que importa é a do DADO escaneado, não a do heartbeat
            const age = j.job === "wallet_scan" ? j.data_age_seconds ?? j.age_seconds : j.age_seconds;
            const title = j.error ?? (j.status === "partial" ? "Atualizou parcialmente (fonte falhou)" : undefined);
            return (
              <li key={j.job} className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium text-foreground/90">
                  {JOB_LABEL[j.job] ?? j.job}
                </span>
                <span className="flex items-center gap-3">
                  <span className="tabular-nums text-foreground/50" title={title}>
                    {fmtAge(age)}
                  </span>
                  <Badge tone={badge.tone}>{badge.label}</Badge>
                </span>
              </li>
            );
          })}
          {jobs.length === 0 && !fresh.isLoading && (
            <li className="text-sm text-foreground/40">Sem jobs registrados ainda.</li>
          )}
        </ul>
      </Card>
    </div>
  );
}
