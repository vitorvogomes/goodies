"use client";

// Botão Importar + painel lateral (560px, Radix: foco preso, Esc fecha, foco volta ao botão).
// Até o Hub de import (Épico 3), lista os imports atuais da v1.
import { UploadIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const IMPORTS = [
  { href: "/ledger/import", label: "Extrato do Nubank", hint: "OFX ou CSV da conta PF ou do MEI" },
  { href: "/portfolio/import", label: "Relatórios da B3", hint: "Movimentação, negociação ou consolidado (.xlsx)" },
];

export function ImportSheet() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button className="w-full lg:w-full">
          <UploadIcon aria-hidden />
          Importar
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="gap-0 data-[side=right]:w-full data-[side=right]:sm:max-w-[560px]">
        <SheetHeader className="border-b border-border">
          <SheetTitle className="type-section-title">Importar</SheetTitle>
          <SheetDescription>
            O Hub de import chega no Épico 3. Por enquanto, os imports atuais:
          </SheetDescription>
        </SheetHeader>
        <ul className="divide-y divide-border">
          {IMPORTS.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                onClick={() => setOpen(false)}
                className="block px-4 py-3 hover:bg-row-highlight"
              >
                <span className="type-body font-semibold">{item.label}</span>
                <span className="type-caption block text-muted-foreground">{item.hint}</span>
              </Link>
            </li>
          ))}
        </ul>
      </SheetContent>
    </Sheet>
  );
}
