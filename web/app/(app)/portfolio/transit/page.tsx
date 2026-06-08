"use client";

// F — reconciliação de trânsito (Pilar 2): quanto saiu do Nubank vs quanto virou posição,
// por trilho. "Em trânsito" = mandado que ainda não virou posição (ex.: relatório B3 com
// atraso). Cripto vem do sleeve à parte (não é trânsito — carteiras lidas ao vivo).
import { Badge, Card } from "@/components/ui";
import { formatBRL } from "@/lib/format";
import { useTransit } from "@/lib/transit";

export default function TransitPage() {
  const { data, isLoading, isError } = useTransit();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="font-mono text-2xl font-semibold text-foreground">Trânsito</h1>
        <p className="mt-1 text-sm text-foreground/50">
          Quanto saiu do Nubank vs quanto virou posição, por trilho. O “em trânsito” é
          dinheiro mandado que ainda não virou posição (ex.: relatório B3 com atraso).
        </p>
      </div>

      {isLoading && <p className="text-sm text-foreground/40">Carregando…</p>}
      {isError && <p className="text-sm text-loss">Falha ao carregar.</p>}

      {data && (
        <>
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-left text-xs text-foreground/50">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Trilho</th>
                  <th className="px-4 py-2.5 text-right font-medium">Saiu</th>
                  <th className="px-4 py-2.5 text-right font-medium">Virou posição</th>
                  <th className="px-4 py-2.5 text-right font-medium">Em trânsito</th>
                </tr>
              </thead>
              <tbody>
                {data.rails.map((r) => (
                  <tr key={r.rail} className="border-t border-border">
                    <td className="px-4 py-2.5 font-medium text-foreground/90">{r.rail}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                      {formatBRL(r.saiu_brl)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-foreground/80">
                      {formatBRL(r.aplicado_brl)}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {r.em_transito_brl > 1 ? (
                        // só "pendente" quando saiu > virou-posição (dinheiro mandado ainda
                        // sem posição). Negativo = posição já cobre o saiu -> conciliado.
                        <span className="tabular-nums text-warning">
                          {formatBRL(r.em_transito_brl)}
                        </span>
                      ) : (
                        <Badge tone="gain">conciliado</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card>
            <h2 className="text-lg font-semibold text-foreground">Cripto (sleeve)</h2>
            <p className="mb-3 mt-1 text-sm text-foreground/50">
              Não é trânsito — as carteiras são lidas ao vivo. É investido vs valor atual.
            </p>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-foreground/60">Investido (líq.)</dt>
              <dd className="text-right tabular-nums">
                {formatBRL(data.crypto.net_invested_brl)}
              </dd>
              <dt className="text-foreground/60">Valor atual</dt>
              <dd className="text-right tabular-nums">
                {formatBRL(data.crypto.current_value_brl)}
              </dd>
              <dt className="text-foreground/60">Resultado</dt>
              <dd
                className={`text-right tabular-nums ${
                  data.crypto.resultado_brl >= 0 ? "text-gain" : "text-loss"
                }`}
              >
                {formatBRL(data.crypto.resultado_brl)}
              </dd>
            </dl>
          </Card>
        </>
      )}
    </div>
  );
}
