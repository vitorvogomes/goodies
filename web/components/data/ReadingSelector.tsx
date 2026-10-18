"use client";

// Seletor de leitura (DESIGN › reading-selector, EXPERIENCE › Seletor de leitura): Mês · Trimestre ·
// Ano · Desde o início, ancorado no mês do Seletor de período; na URL (`?leitura=`), só desta aba
// (o link de aba não a leva). Mesmo visual do alternador Resumo/Detalhado da Tabela de dados.
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { type Leitura, LEITURAS, parseLeitura } from "@/lib/period";
import { cn } from "@/lib/utils";

const LABEL: Record<Leitura, string> = {
  mes: "Mês",
  tri: "Trimestre",
  ano: "Ano",
  inicio: "Desde o início",
};

export function useLeitura(): Leitura {
  return parseLeitura(useSearchParams().get("leitura"));
}

export function ReadingSelector() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const leitura = parseLeitura(params.get("leitura"));
  const pick = (next: Leitura) => {
    const q = new URLSearchParams(params);
    if (next === "mes") q.delete("leitura");
    else q.set("leitura", next);
    router.replace(q.size ? `${pathname}?${q}` : pathname);
  };
  return (
    <div role="group" aria-label="Leitura" className="flex rounded-md bg-muted p-0.5 type-body-sm">
      {LEITURAS.map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={leitura === l}
          onClick={() => pick(l)}
          className={cn("rounded-sm px-2 py-0.5 text-foreground", leitura === l && "bg-background font-semibold")}
        >
          {LABEL[l]}
        </button>
      ))}
    </div>
  );
}
