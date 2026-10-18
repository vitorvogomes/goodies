"use client";

// Tabela de dados (DESIGN.md › data-table, EXPERIENCE › Component Patterns) — TanStack Table v9.
// - Resumo/Detalhado (densidade) lembrado por tabela no navegador;
// - ordenação por coluna (cabeçalho é botão, `aria-sort`), linhas expansíveis por clique ou →/←
//   (↑/↓ andam entre linhas);
// - filtro de texto acima de 20 linhas; rolagem horizontal num contêiner focável, 1ª coluna fixa;
// - números à direita em mono tabular; `<th scope="col">`.
import {
  createSortedRowModel,
  type RowData,
  rowExpandingFeature,
  rowSortingFeature,
  sortFn_alphanumeric,
  sortFn_basic,
  tableFeatures,
  useTable,
} from "@tanstack/react-table";
import { ChevronDownIcon, ChevronRightIcon, ChevronsUpDownIcon } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useMemo, useRef, useState } from "react";

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
  /** Coluna de baixa prioridade: some no modo Resumo antes de rolar. */
  detailOnly?: boolean;
  className?: string;
}

type Density = "resumo" | "detalhado";

const features = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  sortFns: { alphanumeric: sortFn_alphanumeric, basic: sortFn_basic },
  rowExpandingFeature,
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
  caption,
  empty,
}: {
  tableId: string;
  data: T[];
  columns: DataColumn<T>[];
  getRowId: (row: T) => string;
  renderExpanded?: (row: T) => ReactNode;
  caption: string;
  empty?: ReactNode;
}) {
  // A tabela só renderiza no cliente (depois do gate de sessão), então ler o navegador no
  // inicializador não gera diferença de hidratação.
  const [density, setDensity] = useState<Density>(() => readDensity(tableId));
  const [query, setQuery] = useState("");
  const bodyRef = useRef<HTMLTableSectionElement>(null);

  const changeDensity = (d: Density) => {
    setDensity(d);
    try {
      localStorage.setItem(`goodies:table:${tableId}:density`, d);
    } catch {
      /* preferência só local */
    }
  };

  const visible = useMemo(
    () => columns.filter((c) => density === "detalhado" || !c.detailOnly),
    [columns, density],
  );
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
        enableSorting: c.sortable !== false,
        sortFn: c.numeric ? ("basic" as const) : ("alphanumeric" as const),
      })),
    [visible],
  );

  const table = useTable({
    features,
    columns: tableColumns,
    data: filtered,
    getRowId: (row: T) => getRowId(row),
    getRowCanExpand: () => Boolean(renderExpanded),
  });

  const byId = useMemo(() => new Map(visible.map((c) => [c.id, c])), [visible]);
  const cellPad = density === "detalhado" ? "py-1.5" : "py-2";

  function onRowKey(e: KeyboardEvent<HTMLTableRowElement>, toggle: (open?: boolean) => void) {
    // Só a própria linha: teclas de um controle dentro dela (ou de um portal dele) não navegam.
    if (e.target !== e.currentTarget) return;
    const rows = Array.from(bodyRef.current?.querySelectorAll<HTMLElement>("tr[data-row]") ?? []);
    const i = rows.indexOf(e.currentTarget);
    if (e.key === "ArrowRight") toggle(true);
    else if (e.key === "ArrowLeft") toggle(false);
    else if (e.key === "ArrowDown") rows[i + 1]?.focus();
    else if (e.key === "ArrowUp") rows[i - 1]?.focus();
    else if (e.key === "Enter" || e.key === " ") toggle();
    else return;
    e.preventDefault();
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {data.length > 20 ? (
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
                density === d && "bg-background font-semibold",
              )}
            >
              {d === "resumo" ? "Resumo" : "Detalhado"}
            </button>
          ))}
        </div>
      </div>
      <div
        tabIndex={0}
        role="region"
        aria-label={caption}
        className="overflow-x-auto rounded-lg border border-border bg-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
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
                        sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"
                      }
                      className={cn(
                        "type-label px-4 py-2 font-medium whitespace-nowrap text-foreground",
                        col?.numeric ? "text-right" : "text-left",
                        idx === 0 && "sticky z-10 bg-muted",
                        idx === 0 && (renderExpanded ? "left-8" : "left-0"),
                      )}
                    >
                      {header.column.getCanSort() ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="inline-flex items-center gap-1 uppercase"
                        >
                          {col?.header}
                          <ChevronsUpDownIcon aria-hidden className="size-3 text-muted-foreground" />
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
                <td
                  colSpan={visible.length + (renderExpanded ? 1 : 0)}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  {query ? "Nenhuma linha com esse filtro." : empty}
                </td>
              </tr>
            )}
            {table.getRowModel().rows.map((row) => {
              const open = row.getIsExpanded();
              return [
                <tr
                  key={row.id}
                  data-row
                  tabIndex={0}
                  aria-expanded={renderExpanded ? open : undefined}
                  onKeyDown={(e) => onRowKey(e, (v) => row.toggleExpanded(v))}
                  className="group border-t border-border hover:bg-row-highlight focus-visible:bg-row-highlight focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
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
                        onClick={() => row.toggleExpanded()}
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
                          "px-4 whitespace-nowrap",
                          cellPad,
                          col?.numeric && "text-right type-num-table",
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
                    <td colSpan={visible.length} className="px-4 py-3">
                      {renderExpanded(row.original)}
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
