"use client";

// Seção recolhível (v2.2 — F0): card com título, resumo à direita e corpo que abre e fecha. O resumo
// fica visível com a seção fechada, para o dado principal não sumir. `actions` fica fora do botão
// (links e botões próprios não abrem/fecham a seção).
import { ChevronDownIcon } from "lucide-react";
import { type ReactNode, useState } from "react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

export function Section({
  title,
  summary,
  actions,
  defaultOpen = false,
  open: controlled,
  onOpenChange,
  headingLevel = 2,
  className,
  bare = false,
  children,
}: {
  title: ReactNode;
  /** Linha curta ao lado do título (ex.: "12 fechados", total). */
  summary?: ReactNode;
  actions?: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  headingLevel?: 2 | 3;
  className?: string;
  /** Sem a moldura de card (seção dentro de outro card). */
  bare?: boolean;
  children: ReactNode;
}) {
  const [inner, setInner] = useState(defaultOpen);
  const open = controlled ?? inner;
  const setOpen = (v: boolean) => {
    if (controlled === undefined) setInner(v);
    onOpenChange?.(v);
  };
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className={cn(
        !bare && "rounded-lg border border-border bg-card shadow-card",
        className,
      )}
    >
      <div className={cn("flex items-center gap-2", !bare && "px-card-padding")}>
        <Heading className="min-w-0 flex-1">
          <CollapsibleTrigger className="group flex min-h-11 w-full items-center gap-2 py-2 text-left">
            <ChevronDownIcon
              aria-hidden
              className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=closed]:-rotate-90"
            />
            <span className="type-section-title">{title}</span>
            {summary != null && (
              <span className="ml-auto truncate pl-2 type-body-sm text-muted-foreground">{summary}</span>
            )}
          </CollapsibleTrigger>
        </Heading>
        {actions}
      </div>
      <CollapsibleContent className={cn(!bare && "px-card-padding pb-card-padding")}>
        {children}
      </CollapsibleContent>
    </Collapsible>
  );
}
