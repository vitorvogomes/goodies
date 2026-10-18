"use client";

// Ações da linha (coluna "Ações" das tabelas): botões de ícone com rótulo acessível e dica, sempre
// na mesma ordem (editar, depois o resto, excluir por último) e no mesmo lugar — à direita.
import { PencilIcon, Trash2Icon } from "lucide-react";
import type { ComponentType, SVGProps } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface RowAction {
  label: string; // vira aria-label e dica: "Editar Aluguel"
  onClick: () => void;
  icon?: ComponentType<SVGProps<SVGSVGElement>>;
  tone?: "default" | "danger";
  disabled?: boolean;
}

export function RowActions({
  onEdit,
  onDelete,
  extra = [],
  subject,
}: {
  onEdit?: () => void;
  onDelete?: () => void;
  extra?: RowAction[];
  /** O nome da linha, para os rótulos ("Editar {subject}"). */
  subject: string;
}) {
  const actions: RowAction[] = [
    ...(onEdit ? [{ label: `Editar ${subject}`, onClick: onEdit, icon: PencilIcon }] : []),
    ...extra,
    ...(onDelete
      ? [{ label: `Excluir ${subject}`, onClick: onDelete, icon: Trash2Icon, tone: "danger" as const }]
      : []),
  ];
  return (
    <span className="inline-flex items-center justify-end gap-0.5">
      {actions.map((a) => {
        const Icon = a.icon ?? PencilIcon;
        return (
          <Tooltip key={a.label}>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={a.label}
                disabled={a.disabled}
                onClick={(e) => {
                  e.stopPropagation();
                  a.onClick();
                }}
                className={cn(
                  "text-muted-foreground hover:text-foreground",
                  a.tone === "danger" && "hover:text-negative",
                )}
              >
                <Icon aria-hidden className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{a.label}</TooltipContent>
          </Tooltip>
        );
      })}
    </span>
  );
}
