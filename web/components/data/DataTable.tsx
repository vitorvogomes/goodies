"use client";

// Tabela de dados (DESIGN.md › data-table, EXPERIENCE › Component Patterns) — TanStack Table v9.
// - Resumo/Detalhado (densidade) lembrado por tabela no navegador: o Resumo esconde as colunas
//   `detailOnly` e recolhe as linhas; o Detalhado mostra tudo e abre as linhas que têm detalhe;
// - sem rolagem horizontal na largura de trabalho (DESIGN.md:538/542): texto quebra linha (dinheiro
//   nunca) e, se ainda não couber, as colunas de menor prioridade saem primeiro; o que sobrar rola
//   com a borda esmaecida indicando o conteúdo escondido;
// - ordenação por coluna (cabeçalho é botão, `aria-sort`), linhas expansíveis por clique ou →/←
//   (↑/↓ andam entre linhas); filtro de texto acima de 20 linhas; `<th scope="col">`.
import {
  createSortedRowModel,
  type RowData,
  rowSortingFeature,
  sortFn_alphanumeric,
  sortFn_basic,
  tableFeatures,
  useTable,
} from "@tanstack/react-table";
import { ChevronDownIcon, ChevronRightIcon, ChevronsUpDownIcon } from "lucide-react";
import {
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface DataColumn<T extends RowData> {
  id: string;
  header: string;
  /** Valor para ordenar e filtrar. */
  value: (row: T) => string | number | null;
  cell?: (row: T) => ReactNode;
  numeric?: boolean;
  sortable?: boolean;
  /** Coluna de baixa prioridade: só no modo Detalhado. */
  detailOnly?: boolean;
  /** Ordem de saída quando a tabela não cabe (maior sai primeiro). A 1ª coluna e as ações ficam. */
  priority?: 1 | 2 | 3;
  /** Coluna de ações da linha: estreita, à direita, sem cabeçalho visível. */
  actions?: boolean;
  className?: string;
}

type Density = "resumo" | "detalhado";

const features = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  sortFns: { alphanumeric: sortFn_alphanumeric, basic: sortFn_basic },
});

function readDensity(tableId: string): Density {
  try {
    return localStorage.getItem(`goodies:table:${tableId}:density`) === "detalhado"
      ? "detalhado"
      : "resumo";
  } catch {
    return "resumo";
  }
}

export function DataTable<T extends RowData>({
  tableId,
  data,
  columns,
  getRowId,
  renderExpanded,
  renderBelow,
  caption,
  empty,
  filterable = true,
}: {
  tableId: string;
  data: T[];
  columns: DataColumn<T>[];
  getRowId: (row: T) => string;
  renderExpanded?: (row: T) => ReactNode;
  /** Faixa sob a linha (ex.: "Criar regra?"), largura total; null = nada. */
  renderBelow?: (row: T) => ReactNode | null;
  caption: string;
  empty?: ReactNode;
  /** false: a página tem os próprios filtros (ex.: Caixa › Transações). */
  filterable?: boolean;
}) {
  // A tabela só renderiza no cliente (depois do gate de sessão), então ler o navegador no
  // inicializador não gera diferença de hidratação.
  const [density, setDensity] = useState<Density>(() => readDensity(tableId));
  const [query, setQuery] = useState("");
  // Linhas abertas/fechadas à mão — o padrão segue a densidade (Detalhado = todas abertas).
  const [toggled, setToggled] = useState<Set<string>>(() => new Set());
  // Colunas que saíram por falta de espaço (só no Resumo).
  const [dropped, setDropped] = useState<string[]>([]);
  const [edge, setEdge] = useState({ left: false, right: false });
  const bodyRef = useRef<HTMLTableSectionElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const changeDensity = (d: Density) => {
    setDensity(d);
    setToggled(new Set());
    setDropped([]);
    try {
      localStorage.setItem(`goodies:table:${tableId}:density`, d);
    } catch {
      /* preferência só local */
    }
  };

  const visible = useMemo(
    () =>
      columns.filter(
        (c) => (density === "detalhado" || !c.detailOnly) && !dropped.includes(c.id),
      ),
    [columns, density, dropped],
  );
  const hiddenCount = columns.length - visible.length;
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return data;
    return data.filter((row) =>
      columns.some((c) => String(c.value(row) ?? "").toLowerCase().includes(q)),
    );
  }, [data, columns, query]);

  const tableColumns = useMemo(
    () =>
      visible.map((c) => ({
        id: c.id,
        accessorFn: (row: T) => c.value(row),
        header: c.header,
        enableSorting: c.sortable !== false && !c.actions,
        sortFn: c.numeric ? ("basic" as const) : ("alphanumeric" as const),
      })),
    [visible],
  );

  const table = useTable({
    features,
    columns: tableColumns,
    data: filtered,
    getRowId: (row: T) => getRowId(row),
  });

  const byId = useMemo(() => new Map(visible.map((c) => [c.id, c])), [visible]);
  const cellPad = density === "detalhado" ? "py-2.5" : "py-1.5";
  const isOpen = (id: string) =>
    Boolean(renderExpanded) && (density === "detalhado") !== toggled.has(id);
  const toggle = (id: string, open?: boolean) =>
    setToggled((prev) => {
      const next = new Set(prev);
      const want = open ?? !isOpen(id);
      if (want === (density === "detalhado")) next.delete(id);
      else next.add(id);
      return next;
    });

  // Não cabe? Sai a coluna de menor prioridade (Resumo); cabe com folga? Volta tudo e mede de novo.
  const measure = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const overflow = el.scrollWidth - el.clientWidth;
    setEdge({ left: el.scrollLeft > 1, right: overflow - el.scrollLeft > 1 });
    if (density !== "resumo" || overflow <= 1) return;
    const candidates = visible
      .slice(1)
      .filter((c) => !c.actions)
      .map((c) => ({ id: c.id, p: c.priority ?? 2 }))
      .filter((c) => c.p >= 2);
    if (candidates.length === 0) return;
    const worst = candidates.reduce((a, b) => (b.p >= a.p ? b : a));
    setDropped((prev) => (prev.includes(worst.id) ? prev : [...prev, worst.id]));
  }, [density, visible]);

  useLayoutEffect(() => {
    measure();
  }, [measure, filtered]);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    let width = el.clientWidth;
    const observer = new ResizeObserver(() => {
      if (el.clientWidth > width + 24) setDropped([]); // ficou mais larga: tenta mostrar de volta
      width = el.clientWidth;
      measure();
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [measure]);

  function onRowKey(e: KeyboardEvent<HTMLTableRowElement>, id: string) {
    // Só a própria linha: teclas de um controle dentro dela (ou de um portal dele) não navegam.
    if (e.target !== e.currentTarget) return;
    const rows = Array.from(bodyRef.current?.querySelectorAll<HTMLElement>("tr[data-row]") ?? []);
    const i = rows.indexOf(e.currentTarget);
    if (e.key === "ArrowRight" && renderExpanded) toggle(id, true);
    else if (e.key === "ArrowLeft" && renderExpanded) toggle(id, false);
    else if (e.key === "ArrowDown") rows[i + 1]?.focus();
    else if (e.key === "ArrowUp") rows[i - 1]?.focus();
    else if ((e.key === "Enter" || e.key === " ") && renderExpanded) toggle(id);
    else return;
    e.preventDefault();
  }

  const colSpan = visible.length + (renderExpanded ? 1 : 0);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {filterable && data.length > 20 ? (
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filtrar"
            aria-label={`Filtrar ${caption}`}
            className="h-8 max-w-64"
          />
        ) : (
          <span />
        )}
        <div className="flex items-center gap-3">
          {hiddenCount > 0 && density === "resumo" && (
            <span className="type-caption text-muted-foreground">
              {hiddenCount} coluna{hiddenCount > 1 ? "s" : ""} no Detalhado
            </span>
          )}
          <div
            role="group"
            aria-label="Densidade"
            className="flex rounded-md bg-muted p-0.5 type-body-sm"
          >
            {(["resumo", "detalhado"] as const).map((d) => (
              <button
                key={d}
                type="button"
                aria-pressed={density === d}
                onClick={() => changeDensity(d)}
                className={cn(
                  "rounded-sm px-2 py-0.5 text-foreground",
                  density === d && "bg-background font-semibold shadow-xs",
                )}
              >
                {d === "resumo" ? "Resumo" : "Detalhado"}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="relative">
        <div
          ref={scrollRef}
          tabIndex={0}
          role="region"
          aria-label={caption}
          onScroll={() => {
            const el = scrollRef.current;
            if (el)
              setEdge({
                left: el.scrollLeft > 1,
                right: el.scrollWidth - el.clientWidth - el.scrollLeft > 1,
              });
          }}
          className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
        >
          <table className="w-full border-collapse type-body-sm">
            <caption className="sr-only">{caption}</caption>
            <thead className="bg-muted">
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id}>
                  {renderExpanded && (
                    <th scope="col" className="sticky left-0 z-10 w-8 bg-muted" aria-label="Detalhes" />
                  )}
                  {group.headers.map((header, idx) => {
                    const col = byId.get(header.column.id);
                    const sorted = header.column.getIsSorted();
                    return (
                      <th
                        key={header.id}
                        scope="col"
                        aria-sort={
                          col?.actions
                            ? undefined
                            : sorted === "asc"
                              ? "ascending"
                              : sorted === "desc"
                                ? "descending"
                                : "none"
                        }
                        className={cn(
                          "type-label px-3 py-2 align-bottom font-medium text-foreground",
                          col?.numeric || col?.actions ? "text-right" : "text-left",
                          col?.actions && "w-px",
                          idx === 0 && "sticky z-10 bg-muted",
                          idx === 0 && (renderExpanded ? "left-8" : "left-0"),
                        )}
                      >
                        {col?.actions ? (
                          <span className="sr-only">{col.header}</span>
                        ) : header.column.getCanSort() ? (
                          <button
                            type="button"
                            onClick={header.column.getToggleSortingHandler()}
                            className={cn(
                              "inline-flex items-center gap-1 uppercase",
                              col?.numeric && "flex-row-reverse",
                            )}
                          >
                            {col?.header}
                            <ChevronsUpDownIcon aria-hidden className="size-3 shrink-0 text-muted-foreground" />
                          </button>
                        ) : (
                          col?.header
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody ref={bodyRef}>
              {table.getRowModel().rows.length === 0 && (
                <tr>
                  <td colSpan={colSpan} className="px-4 py-8 text-center text-muted-foreground">
                    {query ? "Nenhuma linha com esse filtro." : empty}
                  </td>
                </tr>
              )}
              {table.getRowModel().rows.map((row) => {
                const open = isOpen(row.id);
                return [
                  <tr
                    key={row.id}
                    data-row
                    tabIndex={0}
                    aria-expanded={renderExpanded ? open : undefined}
                    onKeyDown={(e) => onRowKey(e, row.id)}
                    className="group border-t border-border align-top hover:bg-row-highlight focus-visible:bg-row-highlight focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
                  >
                    {renderExpanded && (
                      <td
                        className={cn(
                          "sticky left-0 w-8 bg-card px-2 group-hover:bg-row-highlight group-focus-visible:bg-row-highlight",
                          cellPad,
                        )}
                      >
                        <button
                          type="button"
                          tabIndex={-1}
                          aria-label={open ? "Recolher" : "Expandir"}
                          onClick={() => toggle(row.id)}
                          className="text-muted-foreground"
                        >
                          {open ? (
                            <ChevronDownIcon className="size-4" />
                          ) : (
                            <ChevronRightIcon className="size-4" />
                          )}
                        </button>
                      </td>
                    )}
                    {row.getAllCells().map((cell, idx) => {
                      const col = byId.get(cell.column.id);
                      return (
                        <td
                          key={cell.id}
                          className={cn(
                            "px-3 break-words",
                            cellPad,
                            col?.numeric && "text-right whitespace-nowrap type-num-table",
                            col?.actions && "w-px text-right whitespace-nowrap",
                            idx === 0 &&
                              "sticky bg-card group-hover:bg-row-highlight group-focus-visible:bg-row-highlight",
                            idx === 0 && (renderExpanded ? "left-8" : "left-0"),
                            col?.className,
                          )}
                        >
                          {col?.cell ? col.cell(row.original) : String(col?.value(row.original) ?? "")}
                        </td>
                      );
                    })}
                  </tr>,
                  open && renderExpanded ? (
                    <tr key={`${row.id}-detail`} className="bg-row-highlight">
                      <td />
                      <td colSpan={visible.length} className="px-3 py-3">
                        {renderExpanded(row.original)}
                      </td>
                    </tr>
                  ) : null,
                  (() => {
                    const below = renderBelow?.(row.original);
                    return below ? (
                      <tr key={`${row.id}-below`}>
                        <td colSpan={colSpan} className="px-3 pb-2">
                          {below}
                        </td>
                      </tr>
                    ) : null;
                  })(),
                ];
              })}
            </tbody>
          </table>
        </div>
        {/* conteúdo escondido à direita/esquerda: borda esmaecida (DESIGN.md:542) */}
        {edge.right && (
          <div aria-hidden className="pointer-events-none absolute inset-y-px right-px w-8 rounded-r-lg bg-linear-to-l from-card to-transparent" />
        )}
        {edge.left && (
          <div aria-hidden className="pointer-events-none absolute inset-y-px left-px w-4 rounded-l-lg bg-linear-to-r from-card/60 to-transparent" />
        )}
      </div>
    </div>
  );
}
