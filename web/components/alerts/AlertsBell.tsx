"use client";

// Sino de avisos + Central de avisos (Story 3.1 — FR-14, UX-DR11/13/44). O Sino conta todos os avisos
// ativos (sem vermelho, sem contador quando zero, aria-live polite) e abre o painel lateral de 560px
// com divergências antes de avisos. A ação leva à tela filtrada e fecha o painel; foco no 1º aviso.
import { BellIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { AlertRow } from "@/components/alerts/AlertRow";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAlertCenter, useDismissAlert } from "@/lib/alerts";
import { formatDate } from "@/lib/format";

export function AlertsBell() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [openState, setOpen] = useState(false);
  // "Ver todos" do Painel abre a Central por `?avisos=1`; fechar tira o parâmetro.
  const fromLink = params.get("avisos") === "1";
  const open = openState || fromLink;
  const changeOpen = (value: boolean) => {
    setOpen(value);
    if (!value && fromLink) {
      const next = new URLSearchParams(params);
      next.delete("avisos");
      router.replace(next.size ? `${pathname}?${next}` : pathname);
    }
  };
  const alerts = useAlertCenter();
  const dismiss = useDismissAlert();
  const firstLink = useRef<HTMLAnchorElement>(null);
  const items = alerts.data?.items ?? [];
  const total = alerts.data?.total ?? 0;
  const until = alerts.data?.data_until;

  return (
    <Sheet open={open} onOpenChange={changeOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" aria-label={total ? `Avisos: ${total}` : "Avisos: nenhum"}>
          <BellIcon aria-hidden />
          <span aria-live="polite" className="type-tag min-w-[1ch]">
            {total > 0 ? total : ""}
          </span>
        </Button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="gap-0 data-[side=right]:w-full data-[side=right]:sm:max-w-[560px]"
        onOpenAutoFocus={(e) => {
          if (firstLink.current) {
            e.preventDefault();
            firstLink.current.focus();
          }
        }}
      >
        <SheetHeader className="border-b border-border">
          <SheetTitle className="type-section-title">
            Avisos{total > 0 && <span className="type-num-body"> ({total})</span>}
          </SheetTitle>
          <SheetDescription>Divergências primeiro, depois avisos; mais recentes no topo.</SheetDescription>
        </SheetHeader>
        {alerts.isError && (
          <p className="px-4 py-3 type-body-sm text-negative">Não foi possível carregar os avisos.</p>
        )}
        {alerts.isSuccess && items.length === 0 && (
          <p className="px-4 py-6 type-body text-muted-foreground">
            Nenhum aviso.{until ? ` Dados até ${formatDate(until)}.` : ""}
          </p>
        )}
        <ul className="divide-y divide-border overflow-y-auto">
          {items.map((a, i) => (
            <li key={a.key}>
              <AlertRow
                alert={a}
                linkRef={i === 0 ? firstLink : undefined}
                onNavigate={() => setOpen(false)}
                onDismiss={() =>
                  dismiss.mutate(
                    { key: a.key, fingerprint: a.fingerprint },
                    {
                      onSuccess: () => toast("Aviso dispensado."),
                      onError: () => toast("Não foi possível dispensar. Tente de novo."),
                    },
                  )
                }
              />
            </li>
          ))}
        </ul>
      </SheetContent>
    </Sheet>
  );
}
