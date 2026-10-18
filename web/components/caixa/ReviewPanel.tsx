"use client";

// Revisão de transações (Story 3.10 — FR-9, FR-14, UX-DR19, UX-DR30): painel largo com as pendentes
// do lote (ou todas), agrupadas por mês com subtotais da API. Todas vêm marcadas, com a tag de
// origem. Teclado: ↑↓ movem, Espaço marca, C abre a categoria, Enter confirma; Shift+clique marca o
// intervalo. Trocar a categoria vira "manual". Abre por `?revisar=<lote|todas|mes>` (`mes` = só as do
// `?periodo`, pelo Assistente de recuperação).
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Fragment, type KeyboardEvent, type MouseEvent, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { CategoryCombobox } from "@/components/caixa/CategoryCombobox";
import { RuleProposalStrip } from "@/components/caixa/RuleProposalStrip";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { formatBRL, formatDate, formatMonth, formatSignedBRL } from "@/lib/format";
import { useCategoryOptions, useConfirmReview, useDismissDebenture, useReview } from "@/lib/ledger";
import { cn } from "@/lib/utils";
import type { CategoryOption, ReviewItem, ReviewOrigin } from "@/types/ledger";

const ORIGIN_LABEL: Record<ReviewOrigin, string> = {
  regra: "regra",
  sugestao: "sugestão",
  sem_sugestao: "sem sugestão",
  manual: "manual",
};
const CONFIRM_FAILED = "Não foi possível confirmar as transações. Nada foi perdido.";
// O aporte sugerido só vale enquanto a categoria escolhida segue no trilho de debênture (7.6).
const isDebentureRail = (choice: CategoryOption | undefined) =>
  !choice || choice.key.startsWith("invest:debentures");
const DISMISS_FAILED = "Não foi possível dispensar o aporte. Nada foi perdido. Tentar de novo.";

export function ReviewPanel() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const lote = params.get("revisar");
  const review = useReview(lote, params.get("periodo") ?? undefined);
  // id de um lote de verdade ("todas" e "mes" são filtros, não lote)
  const batchId = lote && lote !== "todas" && lote !== "mes" ? lote : null;
  const options = useCategoryOptions();
  const confirm = useConfirmReview();
  const dismiss = useDismissDebenture();
  const [unchecked, setUnchecked] = useState<Set<string>>(new Set());
  const [choices, setChoices] = useState<Map<string, CategoryOption>>(new Map());
  const [onlyEmpty, setOnlyEmpty] = useState(false);
  // Linhas de regra/sugestão trocadas: mostram a faixa "Criar regra?" (Story 3.11).
  const [proposals, setProposals] = useState<Set<string>>(new Set());
  const [failed, setFailed] = useState(false);
  const lastTouched = useRef<number | null>(null);
  const bodyRef = useRef<HTMLTableSectionElement>(null);
  const retryRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (failed) retryRef.current?.focus();
  }, [failed]);

  // Foco na primeira linha quando os dados chegam (uma vez por abertura).
  const focusedFor = useRef<string | null>(null);
  useEffect(() => {
    if (lote === null) focusedFor.current = null;
    if (!review.isSuccess || lote === null || focusedFor.current === lote) return;
    focusedFor.current = lote;
    requestAnimationFrame(() =>
      bodyRef.current?.querySelector<HTMLElement>("tr[data-row]")?.focus(),
    );
  }, [review.isSuccess, lote]);

  const close = () => {
    const next = new URLSearchParams(params);
    next.delete("revisar");
    setUnchecked(new Set());
    setChoices(new Map());
    setProposals(new Set());
    setFailed(false);
    router.replace(next.size ? `${pathname}?${next}` : pathname);
  };

  const items = review.data?.items ?? [];
  const isEmpty = (it: ReviewItem) => !choices.has(it.id) && it.origin === "sem_sugestao";
  const visible = onlyEmpty ? items.filter(isEmpty) : items;
  const marked = items.filter((it) => !unchecked.has(it.id));
  const markedEmpty = marked.filter(isEmpty).length;
  const canConfirm = marked.length > 0 && markedEmpty === 0 && !confirm.isPending;

  const toggle = (id: string, value?: boolean) =>
    setUnchecked((prev) => {
      const next = new Set(prev);
      const isChecked = !prev.has(id);
      if (value ?? !isChecked) next.delete(id);
      else next.add(id);
      return next;
    });

  function onCheckClick(e: MouseEvent<HTMLInputElement>, index: number, id: string) {
    // Shift+clique: marca (ou desmarca) o intervalo desde a última linha tocada — só mouse.
    if (e.shiftKey && lastTouched.current !== null) {
      const [a, b] = [lastTouched.current, index].sort((x, y) => x - y);
      const value = !unchecked.has(visible[lastTouched.current]?.id ?? id);
      setUnchecked((prev) => {
        const next = new Set(prev);
        for (const it of visible.slice(a, b + 1)) {
          if (value) next.delete(it.id);
          else next.add(it.id);
        }
        return next;
      });
      e.preventDefault();
    } else {
      toggle(id);
    }
    lastTouched.current = index;
  }

  function onRowKey(e: KeyboardEvent<HTMLTableRowElement>, index: number, id: string) {
    if (e.target !== e.currentTarget) return;
    const rows = Array.from(bodyRef.current?.querySelectorAll<HTMLElement>("tr[data-row]") ?? []);
    if (e.key === "ArrowDown") rows[index + 1]?.focus();
    else if (e.key === "ArrowUp") rows[index - 1]?.focus();
    else if (e.key === " ") {
      toggle(id);
      lastTouched.current = index;
    } else if (e.key === "c" || e.key === "C") {
      e.currentTarget.querySelector<HTMLButtonElement>('[role="combobox"]')?.click();
    } else if (e.key === "Enter") {
      if (canConfirm) submit();
    } else return;
    e.preventDefault();
  }

  function submit() {
    setFailed(false);
    confirm.mutate(
      {
        lote: batchId,
        items: marked.map((it) => ({
          transaction_id: it.id,
          category_id: choices.get(it.id)?.id ?? it.category_id,
        })),
      },
      {
        onSuccess: ({ confirmed, remaining }) => {
          toast(
            `${confirmed} ${confirmed === 1 ? "transação confirmada" : "transações confirmadas"}. ` +
              `${remaining} ${remaining === 1 ? "continua" : "continuam"} a revisar.`,
          );
          setChoices(new Map());
          setUnchecked(new Set());
          setProposals(new Set()); // confirmar sem responder à faixa vale como "Agora não"
          if (remaining === 0) close();
        },
        onError: () => setFailed(true),
      },
    );
  }

  const months = new Map((review.data?.months ?? []).map((m) => [m.month, m]));
  const footId = "revisao-rodape";

  return (
    <Sheet open={lote !== null} onOpenChange={(v) => (v ? undefined : close())}>
      <SheetContent
        side="right"
        className="gap-0 data-[side=right]:w-[min(1040px,calc(100vw-48px))] data-[side=right]:sm:max-w-[min(1040px,calc(100vw-48px))]"
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          requestAnimationFrame(() =>
            bodyRef.current?.querySelector<HTMLElement>("tr[data-row]")?.focus(),
          );
        }}
      >
        <SheetHeader className="border-b border-border">
          <SheetTitle className="type-section-title">
            Revisar transações
            {review.data && (
              <span className="type-num-body" aria-live="polite">
                {" "}
                · {marked.length} de {items.length} marcadas
              </span>
            )}
          </SheetTitle>
          <SheetDescription>
            ↑↓ movem · Espaço marca · C troca a categoria · Enter confirma
          </SheetDescription>
        </SheetHeader>
        <div className="flex items-center justify-between gap-2 px-4 py-2">
          <label className="flex items-center gap-2 type-body-sm">
            <input type="checkbox" checked={onlyEmpty} onChange={(e) => setOnlyEmpty(e.target.checked)} />
            Só sem categoria
          </label>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {review.isError && (
            <p className="px-4 py-3 type-body-sm text-negative">Não foi possível carregar a revisão.</p>
          )}
          {review.isSuccess && visible.length === 0 && (
            <div className="px-4 py-8 text-center type-body text-muted-foreground">
              {onlyEmpty ? (
                <>
                  Nenhuma transação sem categoria.{" "}
                  <button type="button" className="text-positive underline" onClick={() => setOnlyEmpty(false)}>
                    Limpar filtro
                  </button>
                </>
              ) : batchId ? (
                "Nada a revisar. Todas as transações do lote vieram de regras."
              ) : (
                "Nada a revisar."
              )}
            </div>
          )}
          {visible.length > 0 && (
            <table className="w-full type-body-sm">
              <caption className="sr-only">Transações a revisar</caption>
              <thead className="sticky top-0 z-10 bg-muted">
                <tr>
                  <th scope="col" className="w-10 px-3 py-2" aria-label="Marcar" />
                  <th scope="col" className="type-label px-2 py-2 text-left font-medium">Data</th>
                  <th scope="col" className="type-label px-2 py-2 text-left font-medium">Descrição</th>
                  <th scope="col" className="type-label px-2 py-2 text-right font-medium">Valor</th>
                  <th scope="col" className="type-label px-2 py-2 text-left font-medium">Categoria</th>
                  <th scope="col" className="type-label px-2 py-2 text-left font-medium">Origem</th>
                </tr>
              </thead>
              <tbody ref={bodyRef}>
                {visible.map((it, index) => {
                  const choice = choices.get(it.id);
                  const origin: ReviewOrigin = choice ? "manual" : it.origin;
                  const checked = !unchecked.has(it.id);
                  const month = months.get(it.month);
                  const firstOfMonth = index === 0 || visible[index - 1].month !== it.month;
                  return (
                    <Fragment key={it.id}>
                      {firstOfMonth && month && months.size > 1 && (
                        <tr className="bg-muted/60">
                          <th colSpan={6} scope="rowgroup" className="px-3 py-1.5 text-left type-label font-medium">
                            {formatMonth(it.month)} · {month.count}{" "}
                            {month.count === 1 ? "transação" : "transações"} · entradas{" "}
                            <span className="type-num-table">{formatBRL(month.entradas)}</span> · saídas{" "}
                            <span className="type-num-table">{formatSignedBRL(month.saidas)}</span>
                          </th>
                        </tr>
                      )}
                      <tr
                        data-row
                        tabIndex={0}
                        aria-selected={checked}
                        onKeyDown={(e) => onRowKey(e, index, it.id)}
                        className={cn(
                          "border-t border-border hover:bg-row-highlight focus-visible:bg-row-highlight focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                          !checked && "text-muted-foreground",
                        )}
                      >
                        <td className="px-3 py-1.5">
                          <input
                            type="checkbox"
                            tabIndex={-1}
                            aria-label={`Marcar ${it.description ?? "transação"}`}
                            checked={checked}
                            onChange={() => undefined}
                            onClick={(e) => onCheckClick(e, index, it.id)}
                          />
                        </td>
                        <td className="px-2 py-1.5 whitespace-nowrap">{formatDate(it.date)}</td>
                        <td className="max-w-80 px-2 py-1.5">
                          <span className="block truncate" title={it.description ?? undefined}>
                            {it.description ?? "—"}
                          </span>
                          <span className="type-caption text-muted-foreground">{it.account_name}</span>
                          {it.debenture && isDebentureRail(choices.get(it.id)) && (
                            <span className="mt-0.5 flex flex-wrap items-center gap-1 type-caption">
                              <span className="font-semibold">Debênture:</span> {it.debenture.label} ·{" "}
                              <span className="type-num-table">{formatBRL(it.debenture.amount)}</span> (sugerido
                              — confirmar a transação registra o aporte)
                              <button
                                type="button"
                                className="text-positive underline disabled:opacity-50"
                                disabled={dismiss.isPending}
                                onClick={() =>
                                  it.debenture &&
                                  dismiss.mutate(it.debenture.contribution_id, {
                                    onSuccess: () => toast("Não é aporte em debênture."),
                                    onError: () => toast(DISMISS_FAILED),
                                  })
                                }
                              >
                                Não é aporte
                              </button>
                            </span>
                          )}
                        </td>
                        <td className="px-2 py-1.5 text-right whitespace-nowrap type-num-table">
                          {formatSignedBRL(it.amount)}
                        </td>
                        <td className="px-2 py-1.5">
                          <CategoryCombobox
                            options={options.data ?? []}
                            value={choice?.id ?? it.category_id}
                            label={choice?.label ?? it.category_label}
                            empty={isEmpty(it)}
                            onSelect={(o) => {
                              setChoices((prev) => new Map(prev).set(it.id, o));
                              toggle(it.id, true);
                              if (
                                (it.origin === "regra" || it.origin === "sugestao") &&
                                o.id !== it.category_id
                              ) {
                                setProposals((prev) => new Set(prev).add(it.id));
                              }
                            }}
                          />
                        </td>
                        <td className="px-2 py-1.5">
                          <StatusBadge tone={origin === "sem_sugestao" ? "warning" : "neutral"}>
                            {ORIGIN_LABEL[origin]}
                          </StatusBadge>
                        </td>
                      </tr>
                      {proposals.has(it.id) && choice && (
                        <tr>
                          <td />
                          <td colSpan={5} className="px-2 pb-2">
                            <RuleProposalStrip
                              transactionId={it.id}
                              categoryId={choice.id}
                              lote={lote && lote !== "todas" ? lote : null}
                              onClose={() =>
                                setProposals((prev) => {
                                  const next = new Set(prev);
                                  next.delete(it.id);
                                  return next;
                                })
                              }
                            />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
        <div className="space-y-2 border-t border-border p-4">
          {failed && (
            <div role="alert" className="flex flex-wrap items-center gap-2 type-body-sm text-negative">
              {CONFIRM_FAILED}
              <Button ref={retryRef} variant="secondary" size="sm" onClick={submit}>
                Tentar de novo
              </Button>
            </div>
          )}
          <div className="flex items-center justify-between gap-2">
            <p id={footId} className="type-body-sm text-muted-foreground" aria-live="polite">
              {markedEmpty > 0
                ? `${markedEmpty} sem categoria. Escolha a categoria ou desmarque a linha.`
                : ""}
            </p>
            <Button ref={confirmRef} disabled={!canConfirm} aria-describedby={footId} onClick={submit}>
              Confirmar {marked.length} {marked.length === 1 ? "transação" : "transações"}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
