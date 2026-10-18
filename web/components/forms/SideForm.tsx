"use client";

// Formulário em painel lateral (DESIGN.md › side-form, EXPERIENCE › Interaction Primitives): título com
// o verbo, campos em uma coluna com rótulo acima e erro sob o campo; rodapé fixo com Salvar (primário) e
// Cancelar (ghost). Esc ou Cancelar com alterações pergunta "Descartar alterações?"; sem alterações,
// fecha direto. Falha ao salvar mostra a mensagem do produto e o foco vai para "Tentar de novo".
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

export const SAVE_FAILED = "Não foi possível salvar. Nada foi perdido.";

export function SideForm({
  open,
  title,
  description,
  dirty,
  saving,
  failed,
  onClose,
  onSubmit,
  children,
}: {
  open: boolean;
  title: string;
  description?: string;
  dirty: boolean;
  saving: boolean;
  failed: boolean;
  onClose: () => void;
  onSubmit: () => void;
  children: ReactNode;
}) {
  const [confirm, setConfirm] = useState(false);
  const retryRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (failed) retryRef.current?.focus();
  }, [failed]);

  const requestClose = () => (dirty ? setConfirm(true) : onClose());
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <>
      <Sheet open={open} onOpenChange={(v) => (v ? undefined : requestClose())}>
        <SheetContent
          side="right"
          className="gap-0 data-[side=right]:w-full data-[side=right]:sm:max-w-[560px]"
        >
          <form onSubmit={submit} noValidate className="flex h-full flex-col">
            <SheetHeader className="border-b border-border">
              <SheetTitle className="type-section-title">{title}</SheetTitle>
              {description && <SheetDescription>{description}</SheetDescription>}
            </SheetHeader>
            <div className="flex-1 space-y-4 overflow-y-auto p-4">{children}</div>
            <div className="space-y-2 border-t border-border p-4">
              {failed && (
                <p role="alert" className="type-body-sm text-negative">
                  {SAVE_FAILED}{" "}
                  <button ref={retryRef} type="submit" className="text-positive underline">
                    Tentar de novo
                  </button>
                </p>
              )}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="ghost" onClick={requestClose}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={saving}>
                  {saving ? "Salvando…" : "Salvar"}
                </Button>
              </div>
            </div>
          </form>
        </SheetContent>
      </Sheet>
      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Descartar alterações?</AlertDialogTitle>
            <AlertDialogDescription>O que você preencheu neste formulário será perdido.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel autoFocus>Continuar editando</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setConfirm(false);
                onClose();
              }}
            >
              Descartar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export function FormField({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="type-body-sm font-semibold">
        {label}
      </label>
      {children}
      {error && (
        <p id={`${id}-erro`} className="type-body-sm text-negative">
          {error}
        </p>
      )}
    </div>
  );
}
