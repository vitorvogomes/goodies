// Linha de aviso (DESIGN.md › alert-item): ponto com halo + tag de severidade em slot de largura fixa
// (todas as mensagens começam no mesmo x) + mensagem + ação em link. Cor nunca é o único sinal: a tag
// nomeia a severidade.
import Link from "next/link";
import type { Ref } from "react";

import { actionHref } from "@/lib/alerts";
import { cn } from "@/lib/utils";
import type { AppAlert } from "@/types/alerts";

const TAG = { divergencia: "divergência", aviso: "aviso" } as const;

export function AlertRow({
  alert,
  onNavigate,
  onDismiss,
  linkRef,
  compact = false,
}: {
  alert: AppAlert;
  onNavigate?: () => void;
  onDismiss?: () => void;
  linkRef?: Ref<HTMLAnchorElement>;
  compact?: boolean;
}) {
  const divergence = alert.severity === "divergencia";
  return (
    <div className={cn("flex items-start gap-3", compact ? "py-1.5" : "px-4 py-3")}>
      <span
        aria-hidden
        className={cn(
          "mt-1.5 size-2 shrink-0 rounded-full ring-4",
          divergence ? "bg-negative ring-negative-tint" : "bg-warning-dot ring-warning-tint",
        )}
      />
      <span
        className={cn(
          "type-tag inline-flex w-[12ch] shrink-0 justify-center rounded-sm px-2",
          divergence ? "bg-negative-tint text-negative" : "bg-warning-tint text-warning",
        )}
      >
        {TAG[alert.severity]}
      </span>
      <div className="min-w-0 flex-1 type-body-sm">
        <p>{alert.message}</p>
        <div className="mt-1 flex gap-3">
          <Link
            ref={linkRef}
            href={actionHref(alert.action)}
            onClick={onNavigate}
            className="text-positive underline"
          >
            {alert.action.label}
          </Link>
          {alert.dismissible && onDismiss && (
            <button type="button" onClick={onDismiss} className="text-muted-foreground underline">
              Dispensar
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
