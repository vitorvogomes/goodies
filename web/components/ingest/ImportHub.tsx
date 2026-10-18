"use client";

// Hub de import (Story 3.9 — FR-1..4, UX-DR17/22/28/33): Bloco Fontes no topo, dropzone, prévia por
// arquivo numa Tabela de dados e "Confirmar import" só depois de todas as prévias. Escolhas na linha
// (conta do CSV, período B3) pedem uma nova prévia. Falha ao confirmar mantém os arquivos e põe o
// foco em "Tentar de novo". Abre pelo botão Importar ou por `?importar=1` (ação dos avisos).
import { UploadIcon, XIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type DragEvent, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { SourcesBlock } from "@/components/ingest/SourcesBlock";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { formatDate } from "@/lib/format";
import { useConfirmImport, usePreviewImport, useReplanImport, useSources } from "@/lib/ingest";
import { useAccounts } from "@/lib/ledger";
import { cn } from "@/lib/utils";
import type { FilePlan, ImportPreview } from "@/types/ingest";

const SOURCE_LABEL: Record<string, string> = {
  nubank_ofx: "Nubank OFX",
  nubank_csv: "Nubank CSV",
  b3_movimentacao: "B3 movimentação",
  b3_negociacao: "B3 negociação",
  b3_consolidado: "B3 consolidado",
};
const CONFIRM_FAILED = "Não foi possível confirmar o import. Nada foi perdido.";

type Row = { name: string; plan: FilePlan | null };

function period(p: FilePlan): string {
  if (!p.period_start || !p.period_end) return "—";
  return p.period_start === p.period_end
    ? formatDate(p.period_end)
    : `${formatDate(p.period_start)} a ${formatDate(p.period_end)}`;
}

export function ImportHub() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [open, setOpen] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [failed, setFailed] = useState(false);
  const [dragging, setDragging] = useState(false);
  const dropRef = useRef<HTMLButtonElement>(null);
  const retryRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sources = useSources();
  const accounts = useAccounts();
  const previewMut = usePreviewImport();
  const replan = useReplanImport();
  const confirm = useConfirmImport();

  // Ação "Importar" dos avisos: ?importar=1 abre o Hub; fechar tira o parâmetro da URL.
  const fromAlert = params.get("importar") === "1";
  const isOpen = open || fromAlert;
  const changeOpen = (value: boolean) => {
    setOpen(value);
    if (!value && fromAlert) {
      const next = new URLSearchParams(params);
      next.delete("importar");
      router.replace(next.size ? `${pathname}?${next}` : pathname);
    }
  };

  useEffect(() => {
    if (failed) retryRef.current?.focus();
  }, [failed]);

  const runPreview = (next: File[]) => {
    setFiles(next);
    setPreview(null);
    setFailed(false);
    if (next.length === 0) return;
    previewMut.mutate(next, {
      onSuccess: setPreview,
      onError: () => toast("Não foi possível ler os arquivos. Tente de novo."),
    });
  };
  const addFiles = (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const known = new Set(files.map((f) => `${f.name}:${f.size}`));
    runPreview([...files, ...Array.from(list).filter((f) => !known.has(`${f.name}:${f.size}`))]);
  };
  const choose = (plan: FilePlan, values: Record<string, string>) => {
    if (!preview) return;
    replan.mutate(
      { batch_id: preview.batch_id, overrides: { [plan.file_hash]: values } },
      { onSuccess: setPreview, onError: () => toast("Não foi possível refazer a prévia.") },
    );
  };

  const reading = previewMut.isPending || replan.isPending;
  const rows: Row[] = files.map((f, i) => ({ name: f.name, plan: preview?.files[i] ?? null }));
  const plans = preview?.files ?? [];
  const pending = plans.some((p) => !p.error && p.needs.length > 0);
  // Confirmar só se algum arquivo trouxer algo novo (transação, operação, posição ou o saldo de um
  // OFX ainda não importado).
  const somethingNew = plans.some(
    (p) => !p.error && (p.new > 0 || (p.reported_balance !== null && !p.already_imported)),
  );
  const canConfirm = !!preview && !reading && !pending && somethingNew && !confirm.isPending;

  function submit() {
    if (!preview) return;
    setFailed(false);
    confirm.mutate(
      { batch_id: preview.batch_id, hash: preview.hash },
      {
        onSuccess: (done) => {
          toast(done.imported === 1 ? "1 item importado." : `${done.imported} itens importados.`);
          const review = done.files.some((p) => p.source?.startsWith("nubank_") && p.new > 0);
          setFiles([]);
          setPreview(null);
          setOpen(false);
          // Havendo transações novas, abre a Revisão de transações (Story 3.10).
          const next = new URLSearchParams(params);
          next.delete("importar");
          if (review) next.set("revisar", done.batch_id);
          if (review || fromAlert) router.push(next.size ? `${pathname}?${next}` : pathname);
        },
        onError: () => setFailed(true),
      },
    );
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const columns: DataColumn<Row>[] = [
    {
      id: "arquivo",
      header: "Arquivo",
      value: (r) => r.name,
      className: "whitespace-normal",
      cell: (r) => (
        <div className="max-w-60 space-y-1">
          <div className="flex items-start gap-1">
            <span className="min-w-0 truncate font-semibold" title={r.name}>
              {r.name}
            </span>
            <button
              type="button"
              aria-label={`Tirar ${r.name}`}
              className="text-muted-foreground"
              onClick={() => runPreview(files.filter((f) => f.name !== r.name))}
            >
              <XIcon className="size-3.5" />
            </button>
          </div>
          {!r.plan && (
            <div role="status" className="space-y-1">
              <span className="type-caption text-muted-foreground">Lendo {r.name}…</span>
              <div className="h-3 w-40 animate-pulse rounded bg-muted" />
            </div>
          )}
          {r.plan && !r.plan.error && (
            <p className="type-caption text-muted-foreground">
              {[
                r.plan.source ? SOURCE_LABEL[r.plan.source] : null,
                r.plan.account_name ?? r.plan.broker,
                r.plan.source?.startsWith("b3_") ? null : period(r.plan),
              ]
                .filter(Boolean)
                .join(" · ")}
              {r.plan.skipped > 0 && ` · ${r.plan.skipped} pulados`}
            </p>
          )}
          {r.plan?.needs.includes("account") && (
            <select
              aria-label={`Conta de ${r.name}`}
              defaultValue=""
              onChange={(e) => r.plan && e.target.value && choose(r.plan, { account_id: e.target.value })}
              className="h-8 rounded-md border border-input bg-background px-2 type-body-sm"
            >
              <option value="">Escolha a conta…</option>
              {(accounts.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          )}
          {r.plan?.source?.startsWith("b3_") && !r.plan.error && (
            <PeriodChoice plan={r.plan} onChoose={(v) => r.plan && choose(r.plan, v)} />
          )}
          {r.plan?.error && <p className="type-caption text-negative">{r.plan.error}</p>}
          {r.plan?.warnings.map((w) => (
            <p key={w} className="type-caption text-warning">
              {w}
            </p>
          ))}
          {r.plan?.already_imported && r.plan.new === 0 && (
            <p className="type-caption text-muted-foreground">Arquivo já importado.</p>
          )}
        </div>
      ),
    },
    { id: "novos", header: "Novos", numeric: true, value: (r) => r.plan?.new ?? null },
    { id: "existentes", header: "Existentes", numeric: true, value: (r) => r.plan?.existing ?? null },
  ];

  return (
    <Sheet open={isOpen} onOpenChange={changeOpen}>
      <SheetTrigger asChild>
        <Button className="w-full lg:w-full">
          <UploadIcon aria-hidden />
          Importar
        </Button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="gap-0 overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-[560px]"
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          dropRef.current?.focus();
        }}
      >
        <SheetHeader className="border-b border-border">
          <SheetTitle className="type-section-title">Importar</SheetTitle>
          <SheetDescription>
            Solte os extratos do Nubank (OFX ou CSV) e os relatórios da B3 (.xlsx). Nada é gravado
            antes de confirmar.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-4 p-4">
          <div className="overflow-hidden rounded-lg border border-border">
            <SourcesBlock sources={sources.data ?? []} loading={sources.isLoading} />
          </div>
          <button
            ref={dropRef}
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cn(
              "flex w-full flex-col items-center gap-1 rounded-lg border-2 border-dashed border-input px-4 py-8 text-center type-body-sm",
              "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none",
              dragging && "bg-row-highlight",
            )}
          >
            <UploadIcon aria-hidden className="size-5 text-muted-foreground" />
            <span className="font-semibold">Arraste os arquivos aqui ou clique para escolher</span>
            <span className="type-caption text-muted-foreground">
              OFX ou CSV do Nubank · movimentação, negociação e consolidado da B3
            </span>
          </button>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".ofx,.csv,.xlsx"
            className="sr-only"
            tabIndex={-1}
            aria-hidden
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = "";
            }}
          />
          {files.length > 0 && (
            <DataTable
              tableId="hub-previa"
              caption="Prévia do import"
              data={rows}
              columns={columns}
              getRowId={(r) => r.name}
            />
          )}
          {failed && (
            <div role="alert" className="flex flex-wrap items-center gap-2 type-body-sm text-negative">
              {CONFIRM_FAILED}
              <Button ref={retryRef} variant="secondary" size="sm" onClick={submit}>
                Tentar de novo
              </Button>
            </div>
          )}
          {files.length > 0 && (
            <div className="flex items-center justify-between gap-2">
              <span className="type-body-sm text-muted-foreground" aria-live="polite">
                {reading
                  ? "Lendo os arquivos…"
                  : pending
                    ? "Escolha o que falta nas linhas marcadas."
                    : preview
                      ? `${preview.new} ${preview.new === 1 ? "item novo" : "itens novos"}.`
                      : ""}
              </span>
              <Button disabled={!canConfirm} onClick={submit}>
                Confirmar import
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function PeriodChoice({
  plan,
  onChoose,
}: {
  plan: FilePlan;
  onChoose: (v: Record<string, string>) => void;
}) {
  const [start, setStart] = useState(plan.period_start ?? "");
  const [end, setEnd] = useState(plan.period_end ?? "");
  const changed = start !== (plan.period_start ?? "") || end !== (plan.period_end ?? "");
  const missing = plan.needs.includes("period");
  return (
    <div className="flex flex-col gap-1">
      <div className="flex gap-1">
        <Input
          type="date"
          aria-label={`Início do período de ${plan.file_name}`}
          value={start}
          onChange={(e) => setStart(e.target.value)}
          className="h-8 w-32 px-1 type-body-sm"
        />
        <Input
          type="date"
          aria-label={`Fim do período de ${plan.file_name}`}
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          className="h-8 w-32 px-1 type-body-sm"
        />
      </div>
      {(changed || missing) && (
        <Button
          size="sm"
          variant="secondary"
          disabled={!start || !end || start > end}
          onClick={() => onChoose({ period_start: start, period_end: end })}
        >
          {missing ? "Usar este período" : "Refazer a prévia"}
        </Button>
      )}
    </div>
  );
}
