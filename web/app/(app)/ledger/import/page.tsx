"use client";

// STORY-01-13-14 — importação de extrato Nubank (.ofx/.csv). Idempotente no backend
// (dedup por FITID); investimento/transferência interna ficam fora do caixa.
import { type FormEvent, useState } from "react";

import { Button, Card, Field, Select } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAccounts, useImportStatement } from "@/lib/ledger";

export default function ImportPage() {
  const accounts = useAccounts();
  const importStatement = useImportStatement();

  const [accountId, setAccountId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!file) {
      setError("Selecione o arquivo do extrato.");
      return;
    }
    importStatement.mutate(
      { accountId: accountId || undefined, file },
      {
        onError: (err) =>
          setError(
            err instanceof ApiError && err.status === 422
              ? "Arquivo não reconhecido (use o .ofx ou .csv do Nubank)."
              : "Falha ao importar. Tente novamente.",
          ),
      },
    );
  }

  const report = importStatement.data;

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="font-mono text-2xl font-semibold text-foreground">Importar extrato</h1>
        <p className="mt-1 text-sm text-foreground/50">
          Exporte o extrato do Nubank (.ofx ou .csv) e importe aqui. Reimportar não duplica.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <Field label="Conta (opcional — OFX detecta pelo nº da conta)" htmlFor="i-account">
          <Select id="i-account" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
            <option value="">Auto-detectar do arquivo</option>
            {(accounts.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
                {a.account_number ? ` (${a.account_number})` : ""}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Arquivo (.ofx / .csv)" htmlFor="i-file">
          <input
            id="i-file"
            type="file"
            accept=".ofx,.csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full text-sm text-foreground/70 file:mr-3 file:rounded-lg file:border-0 file:bg-accent file:px-4 file:py-2 file:text-white hover:file:bg-accent/90"
          />
        </Field>

        {error && (
          <p role="alert" className="text-sm text-loss">
            {error}
          </p>
        )}

        <Button type="submit" disabled={importStatement.isPending}>
          {importStatement.isPending ? "Importando…" : "Importar"}
        </Button>
      </form>

      {report && (
        <Card>
          <p className="mb-3 text-sm text-foreground/50">Resultado da importação</p>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-foreground/60">Linhas lidas</dt>
            <dd className="text-right tabular-nums">{report.parsed}</dd>
            <dt className="text-foreground/60">Importadas</dt>
            <dd className="text-right tabular-nums text-gain">{report.imported}</dd>
            <dt className="text-foreground/60">Duplicadas (ignoradas)</dt>
            <dd className="text-right tabular-nums">{report.duplicates}</dd>
            <dt className="text-foreground/60">Investimento/transferência</dt>
            <dd className="text-right tabular-nums">{report.skipped}</dd>
            <dt className="text-foreground/60">Erros</dt>
            <dd className={`text-right tabular-nums ${report.errors > 0 ? "text-loss" : ""}`}>
              {report.errors}
            </dd>
          </dl>
        </Card>
      )}
    </div>
  );
}
