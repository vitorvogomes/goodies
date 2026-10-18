// Selo de estado (DESIGN.md › status-badge): pílula em tag mono, minúscula; neutro, aviso ou
// divergência — nunca verde (estado bom não é ganho).
import type { ReactNode } from "react";

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
}: {
  tone?: keyof typeof TONES;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "type-tag inline-flex items-center gap-1 rounded-full px-2 whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
