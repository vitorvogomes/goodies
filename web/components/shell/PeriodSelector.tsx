"use client";

// Seletor de período (DESIGN.md › period-selector, EXPERIENCE › Component Patterns): mês em mono
// minúsculo ("out/2026"), ‹ › navegam, popover com os meses. Meses futuros ou antes de jul/2024
// ficam desabilitados com o motivo em tooltip. O Selo de estado (aberto/fechado) chega no Épico 5.
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { formatMonth } from "@/lib/format";
import { MIN_MONTH, currentMonthBRT, isSelectable, shiftMonth } from "@/lib/period";
import { usePeriodo } from "@/lib/use-periodo";
import { cn } from "@/lib/utils";

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

function reason(month: string): string {
  return month < MIN_MONTH ? "Sem dados antes de jul/2024" : "Mês futuro";
}

export function PeriodSelector() {
  const { periodo, setPeriodo } = usePeriodo();
  const [open, setOpen] = useState(false);
  const current = currentMonthBRT();
  const prev = shiftMonth(periodo, -1);
  const next = shiftMonth(periodo, 1);
  const years: number[] = [];
  for (let y = Number(current.slice(0, 4)); y >= Number(MIN_MONTH.slice(0, 4)); y--) years.push(y);

  const nav = (target: string, label: string, Icon: typeof ChevronLeftIcon) => {
    const ok = isSelectable(target);
    const button = (
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={label}
        disabled={!ok}
        onClick={() => setPeriodo(target)}
        className="border-transparent"
      >
        <Icon />
      </Button>
    );
    return ok ? (
      button
    ) : (
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0}>{button}</span>
        </TooltipTrigger>
        <TooltipContent>{reason(target)}</TooltipContent>
      </Tooltip>
    );
  };

  return (
    <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
      {nav(prev, "Mês anterior", ChevronLeftIcon)}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="sm" className="type-num-body border-transparent px-2" aria-label="Escolher mês">
            {formatMonth(periodo)}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 space-y-3">
          {years.map((year) => (
            <div key={year} className="space-y-1">
              <p className="type-label text-muted-foreground">{year}</p>
              <div className="grid grid-cols-4 gap-1">
                {MONTHS.map((label, i) => {
                  const month = `${year}-${String(i + 1).padStart(2, "0")}`;
                  const ok = isSelectable(month);
                  const cell = (
                    <Button
                      variant={month === periodo ? "secondary" : "ghost"}
                      size="sm"
                      disabled={!ok}
                      aria-current={month === periodo ? "date" : undefined}
                      onClick={() => {
                        setPeriodo(month);
                        setOpen(false);
                      }}
                      className={cn("type-num-table w-full border-transparent", !ok && "text-muted-foreground")}
                    >
                      {label}
                    </Button>
                  );
                  return ok ? (
                    <div key={month}>{cell}</div>
                  ) : (
                    <Tooltip key={month}>
                      <TooltipTrigger asChild>
                        <span tabIndex={-1}>{cell}</span>
                      </TooltipTrigger>
                      <TooltipContent>{reason(month)}</TooltipContent>
                    </Tooltip>
                  );
                })}
              </div>
            </div>
          ))}
        </PopoverContent>
      </Popover>
      {nav(next, "Próximo mês", ChevronRightIcon)}
    </div>
  );
}
