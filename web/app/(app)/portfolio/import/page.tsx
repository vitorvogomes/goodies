"use client";

// A5 — importar relatórios B3 (.xlsx): consolidado, movimentação ou negociação.
// Fluxo de 2 passos: pré-visualizar (dry-run) -> confirmar. O backend detecta o tipo
// pela aba e aplica a regra de cobertura (não dobra trade-vs-liquidação). Reimportar
// não duplica (dedup por hash).
import { type FormEvent, useState } from "react";

import { Badge, Button, Card, Field } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useImportB3 } from "@/lib/importB3";
import type { ImportB3Report } from "@/types/portfolio";

const TYPE_LABEL: Record<string, string> = {
  consolidado: "Relatório consolidado",
  movimentacao: "Extrato de movimentação",
  negociacao: "Extrato de negociação",
};

function ReportRows({ report }: { report: ImportB3Report }) {
  return (
    <dl className="grid grid-cols-2 gap-2 text-sm">
      <dt className="text-foreground/60">Tipo de arquivo</dt>
      <dd className="text-right">{TYPE_LABEL[report.file_type] ?? report.file_type}</dd>
      {report.file_type === "consolidado" ? (
        <>
          <dt className="text-foreground/60">
            {report.dry_run ? "Preços a atualizar" : "Preços atualizados"}
          </dt>
          <dd className="text-right tabular-nums text-gain">{report.prices_upserted}</dd>
          {report.prices_skipped_manual > 0 && (
            <>
              <dt className="text-foreground/60">Mantidos manuais (não tocados)</dt>
              <dd className="text-right tabular-nums">{report.prices_skipped_manual}</dd>
            </>
          )}
        </>
      ) : (
        <>
          <dt className="text-foreground/60">Linhas lidas</dt>
          <dd className="text-right tabular-nums">{report.parsed}</dd>
          <dt className="text-foreground/60">
            {report.dry_run ? "A importar" : "Importadas"}
          </dt>
          <dd className="text-right tabular-nums text-gain">{report.imported}</dd>
          <dt className="text-foreground/60">Duplicadas (ignoradas)</dt>
          <dd className="text-right tabular-nums">{report.skipped_duplicate}</dd>
          <dt className="text-foreground/60">Já cobertas (outra fonte)</dt>
          <dd className="text-right tabular-nums">{report.skipped_overlap}</dd>
          {report.date_range && (
            <>
              <dt className="text-foreground/60">Período importado</dt>
              <dd className="text-right tabular-nums">
                {report.date_range[0]} → {report.date_range[1]}
              </dd>
            </>
          )}
        </>
      )}
    </dl>
  );
}

export default function ImportB3Page() {
  const importB3 = useImportB3();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportB3Report | null>(null);
  const [confirmed, setConfirmed] = useState<ImportB3Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  function fail(err: unknown) {
    setError(
      err instanceof ApiError && err.status === 422
        ? "Arquivo não reconhecido (use o .xlsx exportado da B3)."
        : "Falha ao processar. Tente novamente.",
    );
  }

  function pickFile(next: File | null) {
    setFile(next);
    setPreview(null);
    setConfirmed(null);
    setError(null);
  }

  function handlePreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!file) {
      setError("Selecione o arquivo .xlsx da B3.");
      return;
    }
    importB3.mutate({ file, dryRun: true }, { onSuccess: setPreview, onError: fail });
  }

  function handleConfirm() {
    if (!file) return;
    setError(null);
    importB3.mutate(
      { file, dryRun: false },
      {
        onSuccess: (report) => {
          setConfirmed(report);
          setPreview(null);
        },
        onError: fail,
      },
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="font-mono text-2xl font-semibold text-foreground">Importar B3</h1>
        <p className="mt-1 text-sm text-foreground/50">
          Suba o .xlsx da B3 (consolidado, movimentação ou negociação). Veja a prévia
          antes de confirmar; reimportar não duplica.
        </p>
      </div>

      <form onSubmit={handlePreview} className="space-y-5">
        <Field label="Arquivo (.xlsx)" htmlFor="b3-file">
          <input
            id="b3-file"
            type="file"
            accept=".xlsx"
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            className="w-full text-sm text-foreground/70 file:mr-3 file:rounded-lg file:border-0 file:bg-accent file:px-4 file:py-2 file:text-white hover:file:bg-accent/90"
          />
        </Field>

        {error && (
          <p role="alert" className="text-sm text-loss">
            {error}
          </p>
        )}

        <Button type="submit" disabled={importB3.isPending || !file}>
          {importB3.isPending && !confirmed ? "Lendo…" : "Pré-visualizar"}
        </Button>
      </form>

      {preview && (
        <Card>
          <p className="mb-3 text-sm text-foreground/50">Prévia (nada foi gravado)</p>
          <ReportRows report={preview} />
          {preview.new_tickers.length > 0 && (
            <p className="mt-3 text-sm">
              <Badge tone="warning">Tickers novos</Badge>{" "}
              <span className="text-foreground/70">
                {preview.new_tickers.join(", ")} — confira a categoria depois.
              </span>
            </p>
          )}
          {preview.overlap_tickers.length > 0 && (
            <p className="mt-2 text-xs text-foreground/50">
              Já cobertos por outra fonte (pulados): {preview.overlap_tickers.join(", ")}.
            </p>
          )}
          <Button
            type="button"
            onClick={handleConfirm}
            disabled={importB3.isPending}
            className="mt-4"
          >
            {importB3.isPending
              ? "Importando…"
              : preview.file_type === "consolidado"
                ? `Aplicar preços (${preview.prices_upserted})`
                : `Confirmar import (${preview.imported})`}
          </Button>
        </Card>
      )}

      {confirmed && (
        <Card>
          <p className="mb-3 text-sm text-gain">Importado com sucesso</p>
          <ReportRows report={confirmed} />
        </Card>
      )}
    </div>
  );
}
