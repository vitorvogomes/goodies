"use client";

// E4 — painel de frescor (Pilar 0). O app é local-on-demand: os dados se atualizam ao
// abrir (catch-up no AppShell) ou no botão "Atualizar tudo". Cada fonte só atualiza
// quando vencida (respeita os limites das APIs).
import { Badge, Button, Card } from "@/components/ui";
import { useFreshness, useRefreshAll } from "@/lib/jobs";

const JOB_LABEL: Record<string, string> = {
  price_b3: "Preços B3 / Tesouro",
  price_crypto: "Preços cripto",
  wallet_scan: "Carteiras (scan)",
  benchmark: "Índices (CDI/IPCA)",
};

function fmtAge(seconds: number | null): string {
  if (seconds == null) return "nunca rodou";
  const hours = seconds / 3600;
  if (hours < 1) return `há ${Math.max(1, Math.round(seconds / 60))} min`;
  if (hours < 48) return `há ${Math.round(hours)}h`;
  return `há ${Math.round(hours / 24)}d`;
}

export default function RefreshPage() {
  const fresh = useFreshness();
  const refresh = useRefreshAll();
  const jobs = fresh.data ?? [];

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-mono text-2xl font-semibold text-foreground">Atualização</h1>
        <Button type="button" onClick={() => refresh.mutate(true)} disabled={refresh.isPending}>
          {refresh.isPending ? "Atualizando…" : "Atualizar tudo"}
        </Button>
      </div>
      <p className="text-sm text-foreground/50">
        O app é local: os dados se atualizam quando você abre ou clica acima. Cada fonte só
        atualiza quando vencida (respeitando os limites das APIs gratuitas).
      </p>

      <Card>
        <ul className="space-y-3">
          {jobs.map((j) => (
            <li key={j.job} className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium text-foreground/90">
                {JOB_LABEL[j.job] ?? j.job}
              </span>
              <span className="flex items-center gap-3">
                <span
                  className="tabular-nums text-foreground/50"
                  title={j.error ?? undefined}
                >
                  {fmtAge(j.age_seconds)}
                </span>
                {j.ok === false ? (
                  <Badge tone="loss">erro</Badge>
                ) : j.stale ? (
                  <Badge tone="warning">vencido</Badge>
                ) : (
                  <Badge tone="gain">fresco</Badge>
                )}
              </span>
            </li>
          ))}
          {jobs.length === 0 && !fresh.isLoading && (
            <li className="text-sm text-foreground/40">Sem jobs registrados ainda.</li>
          )}
        </ul>
      </Card>
    </div>
  );
}
