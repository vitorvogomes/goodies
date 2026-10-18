// Selo de estado (DESIGN.md › status-badge): pílula em tag mono, minúscula; neutro, aviso ou
// divergência — nunca verde (estado bom não é ganho). Com `tooltip`, explica o estado ao passar o
// mouse ou focar (ex.: "o IPCA de out/2026 ainda não saiu").
import type { ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const TONES = {
  neutral: "bg-secondary text-secondary-foreground",
  warning: "bg-warning-tint text-warning",
  divergence: "bg-negative-tint text-negative",
} as const;

export function StatusBadge({
  tone = "neutral",
  children,
  className,
  tooltip,
}: {
  tone?: keyof typeof TONES;
  children: ReactNode;
  className?: string;
  tooltip?: string;
}) {
  const badge = (
    <span
      tabIndex={tooltip ? 0 : undefined}
      className={cn(
        "type-tag inline-flex items-center gap-1 rounded-full px-2 whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
  if (!tooltip) return badge;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  );
}
