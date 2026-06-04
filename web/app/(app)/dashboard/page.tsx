"use client";

// STORY-01-12 — dashboard de caixa: resumo mensal + taxa de poupança, projeção
// 30/60/90, alertas e tendência de poupança (barras CSS, sem libs novas).
import { Card } from "@/components/ui";
import { formatBRL, formatMonth, formatPercent } from "@/lib/format";
import { useAlerts, useMonthlySummaries, useProjection } from "@/lib/ledger";
import type { MonthlySummary } from "@/types/ledger";

function Stat({ label, value, tone }: { label: string; value: string; tone?: "gain" | "loss" }) {
  const color = tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-foreground";
  return (
    <Card>
      <p className="text-sm text-foreground/50">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${color}`}>{value}</p>
    </Card>
  );
}

function SummaryCards({ month }: { month: MonthlySummary }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Receita do mês" value={formatBRL(month.total_income)} tone="gain" />
      <Stat label="Despesa do mês" value={formatBRL(month.total_expense)} tone="loss" />
      <Stat
        label="Saldo do mês"
        value={formatBRL(month.net_cashflow)}
        tone={month.net_cashflow < 0 ? "loss" : "gain"}
      />
      <Stat label="Taxa de poupança" value={formatPercent(month.savings_rate)} tone="gain" />
    </div>
  );
}

function SavingsTrend({ months }: { months: MonthlySummary[] }) {
  // months vem do mais recente p/ o mais antigo; mostra os últimos 6 em ordem cronológica.
  const data = [...months].slice(0, 6).reverse();
  return (
    <Card>
      <p className="mb-4 text-sm text-foreground/50">Taxa de poupança (últimos meses)</p>
      <div className="flex h-40 items-end gap-3">
        {data.map((m) => (
          <div key={m.month} className="flex flex-1 flex-col items-center gap-1.5">
            <span className="text-xs tabular-nums text-foreground/60">
              {Math.round(m.savings_rate)}%
            </span>
            <div className="flex w-full flex-1 items-end">
              <div
                className="w-full rounded-t bg-gain/70"
                style={{ height: `${Math.max(2, Math.min(100, m.savings_rate))}%` }}
              />
            </div>
            <span className="text-xs text-foreground/40">{formatMonth(m.month)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const summaries = useMonthlySummaries();
  const projection = useProjection();
  const alerts = useAlerts();

  const latest = summaries.data?.[0];

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-2xl font-semibold text-foreground">Dashboard</h1>

      {projection.data && (
        <Stat
          label="Saldo Acumulado"
          value={formatBRL(projection.data.current_balance)}
          tone={projection.data.current_balance < 0 ? "loss" : "gain"}
        />
      )}

      {summaries.isLoading && <p className="text-foreground/50">Carregando…</p>}
      {summaries.isError && <p className="text-loss">Erro ao carregar o resumo.</p>}
      {summaries.data && !latest && (
        <p className="text-foreground/50">Sem transações ainda. Adicione a primeira em “Nova transação”.</p>
      )}

      {latest && <SummaryCards month={latest} />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {summaries.data && summaries.data.length > 0 && <SavingsTrend months={summaries.data} />}

        <Card>
          <p className="mb-4 text-sm text-foreground/50">Projeção de caixa</p>
          {projection.isLoading && <p className="text-foreground/50">Carregando…</p>}
          {projection.data && (
            <div className="space-y-2">
              {projection.data.projections.map((p) => (
                <div key={p.days} className="flex justify-between text-sm">
                  <span className="text-foreground/60">{p.days} dias</span>
                  <span
                    className={`tabular-nums ${
                      p.projected_balance < 0 ? "text-loss" : "text-foreground"
                    }`}
                  >
                    {formatBRL(p.projected_balance)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card>
        <p className="mb-3 text-sm text-foreground/50">Alertas</p>
        {alerts.isLoading && <p className="text-foreground/50">Carregando…</p>}
        {alerts.data && alerts.data.length === 0 && (
          <p className="text-sm text-foreground/50">Nenhum alerta no momento.</p>
        )}
        <ul className="space-y-2">
          {(alerts.data ?? []).map((a, i) => (
            <li key={`${a.type}-${i}`} className="flex items-start gap-2 text-sm">
              <span aria-hidden className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-warning" />
              <span className="text-foreground/80">{a.message}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
