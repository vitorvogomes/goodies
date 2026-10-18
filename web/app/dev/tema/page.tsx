"use client";

// Theme-showcase (Story 1.5 — UX-DR4): todos os tokens e componentes existentes, em todos os
// estados, no claro e no escuro lado a lado. Só existe com `pnpm dev` (NODE_ENV=development).
// Regra (conventions.md): toda story que cria componente o acrescenta aqui.
import { notFound } from "next/navigation";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Suspense, useState } from "react";

import { ReapplyDiff } from "@/components/ajustes/ReapplyDiff";
import { AlertRow } from "@/components/alerts/AlertRow";
import { CategoryCombobox } from "@/components/caixa/CategoryCombobox";
import { type DataColumn, DataTable } from "@/components/data/DataTable";
import { StatusBadge } from "@/components/data/StatusBadge";
import { FormField, SideForm } from "@/components/forms/SideForm";
import { ImportHub } from "@/components/ingest/ImportHub";
import { SourcesBlock } from "@/components/ingest/SourcesBlock";
import { PeriodSelector } from "@/components/shell/PeriodSelector";
import { ThemeSwitch } from "@/components/shell/ThemeSwitch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatBRL } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AppAlert } from "@/types/alerts";

const COLORS = [
  "background", "foreground", "card", "card-foreground", "popover", "popover-foreground",
  "muted", "muted-foreground", "border", "input", "ring", "row-highlight", "primary",
  "primary-foreground", "secondary", "secondary-foreground", "accent", "accent-foreground",
  "positive", "negative", "destructive", "destructive-foreground", "warning", "warning-dot",
  "positive-tint", "negative-tint", "warning-tint", "sidebar", "sidebar-foreground",
  "sidebar-primary", "sidebar-accent", "sidebar-border", "chart-1", "chart-2", "chart-3",
];
const TYPE = [
  ["type-page-title", "Título da página"],
  ["type-section-title", "Título de seção"],
  ["type-body", "Corpo 14px"],
  ["type-body-sm", "Corpo 13px (tabela)"],
  ["type-label", "Rótulo de KPI"],
  ["type-caption", "até 14/10/2026"],
  ["type-num-display", "R$ 68.695,66"],
  ["type-num-lg", "R$ 2.200,00"],
  ["type-num-body", "R$ 1.700,00"],
  ["type-num-table", "−R$ 163,80"],
  ["type-tag", "a caminho"],
] as const;
const RADII = ["rounded-xs", "rounded-sm", "rounded-md", "rounded-lg", "rounded-xl", "rounded-full"];

type Demo = { id: string; nome: string; valor: number; origem: string };
const DEMO: Demo[] = [
  { id: "1", nome: "Mercado", valor: -412.3, origem: "regra" },
  { id: "2", nome: "Recorrente", valor: 8781.08, origem: "manual" },
  { id: "3", nome: "Uber", valor: -32.9, origem: "sugestão" },
];
const DEMO_COLS: DataColumn<Demo>[] = [
  { id: "nome", header: "Descrição", value: (d) => d.nome },
  { id: "valor", header: "Valor", value: (d) => d.valor, numeric: true, cell: (d) => formatBRL(d.valor) },
  { id: "origem", header: "Origem", value: (d) => d.origem, cell: (d) => <StatusBadge>{d.origem}</StatusBadge> },
];
const DEMO_OPTIONS = [
  { id: "a", key: "gasto:alimentacao", name: "Mercado", label: "Alimentação › Mercado", group_key: "alimentacao", group_name: "Alimentação", kind: "expense", role: "consumo", is_active: true },
  { id: "b", key: "gasto:transporte", name: "Transporte", label: "Transporte › Transporte", group_key: "transporte", group_name: "Transporte", kind: "expense", role: "consumo", is_active: true },
];

function SideFormDemo({ failed = false }: { failed?: boolean }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        {failed ? "Formulário (falha ao salvar)" : "Formulário em painel lateral"}
      </Button>
      <SideForm
        open={open}
        title="Novo custo fixo"
        dirty={value !== ""}
        saving={false}
        failed={failed}
        onClose={() => setOpen(false)}
        onSubmit={() => setOpen(false)}
      >
        <FormField id="demo-nome" label="Nome" error={value === "" ? "Informe o nome." : null}>
          <Input id="demo-nome" value={value} onChange={(e) => setValue(e.target.value)} />
        </FormField>
      </SideForm>
    </>
  );
}

const DEMO_ALERTS: AppAlert[] = [
  {
    key: "saldo_divergente:pf",
    fingerprint: "a",
    severity: "divergencia",
    message: "Saldo divergente em R$\u00a037,20 na conta PF.",
    action: { label: "Ver transações", route: "/caixa/transacoes", params: { periodo: "2026-10" } },
    as_of: "2026-10-16",
    dismissible: true,
  },
  {
    key: "custo_fixo_vencendo:1",
    fingerprint: "b",
    severity: "aviso",
    message: "Internet vence em 20/10/2026.",
    action: { label: "Ver custos fixos", route: "/ajustes/custos-fixos", params: {} },
    as_of: "2026-10-18",
    dismissible: true,
  },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="type-section-title">{title}</h2>
      {children}
    </section>
  );
}

function Panel({ mode }: { mode: "theme-light" | "dark" }) {
  return (
    <div className={cn(mode, "min-w-0 flex-1 space-y-section-gap bg-background p-6 text-foreground")}>
      <h1 className="type-page-title">{mode === "dark" ? "Escuro" : "Claro"}</h1>

      <Section title="Cores">
        <div className="grid grid-cols-3 gap-2">
          {COLORS.map((c) => (
            <div key={c} className="flex items-center gap-2">
              <span
                className="size-6 shrink-0 rounded-sm border border-input"
                style={{ background: `var(--${c})` }}
              />
              <span className="type-caption truncate text-muted-foreground">{c}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Tipografia">
        <div className="space-y-1">
          {TYPE.map(([cls, text]) => (
            <div key={cls} className="flex items-baseline justify-between gap-4">
              <span className={cls}>{text}</span>
              <span className="type-caption text-muted-foreground">{cls}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Raios">
        <div className="flex gap-3">
          {RADII.map((r) => (
            <div key={r} className={cn(r, "size-12 border border-input bg-muted")} title={r} />
          ))}
        </div>
      </Section>

      <Section title="Botões">
        <div className="flex flex-wrap gap-2">
          <Button>Primário</Button>
          <Button variant="secondary">Secundário</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Desfazer</Button>
          <Button variant="link">Link</Button>
          <Button disabled>Desabilitado</Button>
        </div>
      </Section>

      <Section title="Campos">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor={`${mode}-a`}>Normal</Label>
            <Input id={`${mode}-a`} placeholder="Descrição" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${mode}-b`}>Inválido</Label>
            <Input id={`${mode}-b`} aria-invalid defaultValue="abc" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${mode}-c`}>Desabilitado</Label>
            <Input id={`${mode}-c`} disabled defaultValue="R$ 0,00" />
          </div>
          <div className="space-y-1.5">
            <Label>Select</Label>
            <Select defaultValue="mes">
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mes">Mês</SelectItem>
                <SelectItem value="tri">Trimestre</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </Section>

      <Section title="Selos">
        <div className="flex flex-wrap gap-2">
          <Badge>padrão</Badge>
          <Badge variant="secondary">secundário</Badge>
          <Badge variant="outline">contorno</Badge>
        </div>
      </Section>

      <Section title="Card">
        <Card className="shadow-card">
          <CardHeader>
            <CardTitle className="type-label text-muted-foreground">Patrimônio</CardTitle>
            <CardDescription className="type-caption">até 14/10/2026</CardDescription>
          </CardHeader>
          <CardContent className="type-num-display">R$ 68.695,66</CardContent>
        </Card>
      </Section>

      <Section title="Abas (linha)">
        <Tabs defaultValue="posicoes">
          <TabsList variant="line">
            <TabsTrigger value="posicoes">Posições</TabsTrigger>
            <TabsTrigger value="aportes">Aportes</TabsTrigger>
            <TabsTrigger value="conciliacao" disabled>
              Conciliação
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </Section>

      <Section title="Formulário em painel lateral">
        <div className="flex flex-wrap gap-2">
          <SideFormDemo />
          <SideFormDemo failed />
        </div>
      </Section>

      <Section title="Selo de estado">
        <div className="flex flex-wrap gap-2">
          <StatusBadge tooltip="Saldo do extrato bate ao centavo até 16/10/2026.">conferido</StatusBadge>
          <StatusBadge tone="warning">a revisar</StatusBadge>
          <StatusBadge tone="divergence">divergente</StatusBadge>
        </div>
      </Section>

      <Section title="Combobox de categoria">
        <div className="flex gap-2">
          <CategoryCombobox options={DEMO_OPTIONS} value="a" label="Alimentação › Mercado" onSelect={() => {}} />
          <CategoryCombobox options={DEMO_OPTIONS} value={null} label="sem sugestão" empty onSelect={() => {}} />
        </div>
      </Section>

      <Section title="Tabela de dados">
        <DataTable
          tableId={`tema-${mode}`}
          caption="Exemplo"
          data={DEMO}
          columns={DEMO_COLS}
          getRowId={(d) => d.id}
          renderExpanded={(d) => <span className="type-body-sm">Detalhe de {d.nome}</span>}
        />
      </Section>

      <Section title="Linha de aviso">
        <ul className="divide-y divide-border rounded-lg border border-border bg-card shadow-card">
          {DEMO_ALERTS.map((a) => (
            <li key={a.key}>
              <AlertRow alert={a} onDismiss={() => toast("Aviso dispensado.")} />
            </li>
          ))}
        </ul>
        <AlertRow alert={DEMO_ALERTS[1]} compact />
      </Section>

      <Section title="Prévia de reaplicação (antes × depois)">
        <ReapplyDiff
          preview={{
            changes: [
              {
                transaction_id: "r1",
                date: "2026-10-03",
                description: "UBER *TRIP",
                amount: -23.9,
                before: "Lazer › Lazer",
                after: "Transporte › Transporte",
                rule_pattern: "uber",
              },
            ],
            manual_unchanged: 2,
            closed_months: 1,
          }}
        />
      </Section>

      <Section title="Seletor de período">
        <Suspense>
          <PeriodSelector />
        </Suspense>
      </Section>

      <Section title="Botão Importar e Hub de import">
        <div className="w-60">
          <Suspense>
            <ImportHub />
          </Suspense>
        </div>
      </Section>

      <Section title="Bloco Fontes">
        <div className="overflow-hidden rounded-lg border border-border">
          <SourcesBlock
            sources={[
              { key: "nubank_pf", label: "Nubank PF", kind: "OFX ou CSV", updated_until: "2026-10-16", stale: false, balance_status: "divergente", balance_as_of: "2026-10-16", balance_difference: 37.2 },
              { key: "nubank_mei", label: "Nubank MEI", kind: "OFX ou CSV", updated_until: "2026-08-31", stale: true, balance_status: null, balance_as_of: null, balance_difference: null },
            ]}
          />
        </div>
      </Section>

      <Section title="Switch de tema e Toast">
        <div className="flex items-center gap-2">
          <ThemeSwitch />
          <Button variant="secondary" onClick={() => toast("Lote importado: 42 transações")}>
            Mostrar toast
          </Button>
        </div>
      </Section>
    </div>
  );
}

export default function TemaPage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return (
    <div className="flex min-h-screen flex-1">
      <Panel mode="theme-light" />
      <Panel mode="dark" />
    </div>
  );
}
