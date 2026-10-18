"use client";

// Combobox de categoria (DESIGN.md › category-combobox): Command em Popover, opções "Grupo ›
// Subcategoria", busca ("merc" → "Alimentação › Mercado"), ↑↓ + Enter escolhem, Esc fecha sem
// mudar. Arquivadas não aparecem. Vazio ("sem sugestão") com borda de aviso.
import { ChevronsUpDownIcon } from "lucide-react";
import { useId, useState } from "react";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { CategoryOption } from "@/types/ledger";

export function CategoryCombobox({
  options,
  value,
  label,
  onSelect,
  disabled,
  empty,
}: {
  options: CategoryOption[];
  value: string | null;
  label: string;
  onSelect: (option: CategoryOption) => void;
  disabled?: boolean;
  empty?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const groups = new Map<string, CategoryOption[]>();
  for (const o of options) {
    if (!o.is_active) continue;
    groups.set(o.group_name, [...(groups.get(o.group_name) ?? []), o]);
  }
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-label={`Categoria: ${label}`}
          disabled={disabled}
          className={cn(
            "inline-flex h-7 max-w-64 min-w-40 items-center justify-between gap-2 rounded-md border bg-background px-2 text-left type-body-sm",
            empty ? "border-warning" : "border-input",
            "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none disabled:opacity-50",
          )}
        >
          <span className="truncate">{label}</span>
          <ChevronsUpDownIcon aria-hidden className="size-3 shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent id={listId} className="w-80 p-0" align="start">
        <Command
          filter={(itemValue, search) =>
            itemValue.toLowerCase().includes(search.trim().toLowerCase()) ? 1 : 0
          }
        >
          <CommandInput placeholder="Buscar categoria" />
          <CommandList>
            <CommandEmpty>Nenhuma categoria.</CommandEmpty>
            {[...groups.entries()].map(([group, items]) => (
              <CommandGroup key={group} heading={group}>
                {items.map((o) => (
                  <CommandItem
                    key={o.id}
                    value={o.label}
                    data-checked={o.id === value}
                    onSelect={() => {
                      setOpen(false);
                      if (o.id !== value) onSelect(o);
                    }}
                  >
                    {o.label}
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
