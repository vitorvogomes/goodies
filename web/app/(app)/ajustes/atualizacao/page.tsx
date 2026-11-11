"use client";

// Ajustes › Atualização (Story 10.3 — FR-14, FR-35, AR11): cada job (preços B3 e Tesouro, cripto,
// carteiras, índices, renda fixa pelo CDI, backup) com última execução, último sucesso, próxima
// execução e erro, em horário de Brasília. "Atualizar tudo" roda o catch-up (a Binance só no
// horário agendado) e mostra o resultado por job. É o destino da ação dos avisos de worker.
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/button";
import { fmtWhen } from "@/lib/format";
import { useFreshness, useRefreshAll, useRefreshRunning } from "@/lib/jobs";
import type { JobStatus } from "@/types/jobs";

const STATE: Record<JobStatus["status"], { text: string; tone: "neutral" | "warning" | "divergence" }> = {
  fresh: { text: "em dia", tone: "neutral" },
  stale: { text: "atrasado", tone: "warning" },
  partial: { text: "parcial", tone: "warning" },
  error: { text: "erro", tone: "divergence" },
};

const RESULT: Record<string, string> = {
  ok: "atualizado",
  ran: "atualizado",
  skipped: "em dia (não precisou)",
  fresh: "em dia (não precisou)",
  error: "falhou",
  failed: "falhou",
};

export default function AtualizacaoPage() {
  const running = useRefreshRunning();
  const status = useFreshness(running);
  const refresh = useRefreshAll();
  const result = refresh.data;

  if (status.isError && !status.data) {
    return <p className="type-body text-negative">Não foi possível carregar o estado das atualizações.</p>;
  }
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="type-caption text-muted-foreground">Horários em Brasília.</p>
        <Button onClick={() => refresh.mutate(true)} disabled={running}>
          {running ? "Atualizando…" : "Atualizar tudo"}
        </Button>
      </div>
      {result && (
        <div role="status" className="rounded-lg border border-border bg-card shadow-card p-card-padding type-body-sm">
          {result.status === "already_running" ? (
            "Já havia uma atualização rodando."
          ) : (
            <ul className="space-y-0.5">
              {Object.entries(result.jobs).map(([job, outcome]) => (
                <li key={job}>
                  {status.data?.find((j) => j.job === job)?.label ?? job}: {RESULT[outcome] ?? outcome}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {refresh.isError && (
        <p role="alert" className="type-body-sm text-negative">
          Não foi possível atualizar. Nada foi perdido. Tentar de novo.
        </p>
      )}
      {!status.data ? (
        <div className="h-48 animate-pulse rounded-lg border border-border bg-card shadow-card" aria-hidden />
      ) : (
        <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card">
          <table className="table-stack w-full type-body-sm">
            <caption className="sr-only">Atualizações automáticas</caption>
            <thead className="bg-muted text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 text-left font-medium">Atualização</th>
                <th scope="col" className="px-4 py-2 text-left font-medium">Estado</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Última execução</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Último sucesso</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Próxima</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {status.data.map((j) => (
                <tr key={j.job}>
                  <th scope="row" className="px-4 py-2 text-left font-normal">
                    {j.label || j.job}
                    {j.note && <span className="block type-caption text-muted-foreground">{j.note}</span>}
                    {j.error && <span className="block type-caption text-negative">{j.error}</span>}
                  </th>
                  <td data-label="Estado" className="px-4 py-2">
                    <StatusBadge tone={STATE[j.status].tone}>{STATE[j.status].text}</StatusBadge>
                  </td>
                  <td data-label="Última execução" className="px-4 py-2 text-right type-num-table">{fmtWhen(j.last_run)}</td>
                  <td data-label="Último sucesso" className="px-4 py-2 text-right type-num-table">{fmtWhen(j.last_success_at)}</td>
                  <td data-label="Próxima" className="px-4 py-2 text-right type-num-table">{fmtWhen(j.next_run)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
