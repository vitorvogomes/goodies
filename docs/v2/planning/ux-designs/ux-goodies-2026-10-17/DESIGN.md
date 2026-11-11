---
title: "DESIGN — Goodies v2"
status: final
created: 2026-10-17
updated: 2026-10-18
name: Goodies
description: Painel de finanças pessoais do Vitor. shadcn/ui + Radix + Tailwind v4 sobre Next.js; neutros tweakcn darkmatter + verde tweakcn supabase; claro e escuro. Este arquivo especifica só o delta sobre os padrões do shadcn.
colors:
  # Convenção: a chave sem sufixo é o modo CLARO; a chave com sufixo -dark é o modo ESCURO.
  # Toda referência {colors.x} resolve para x no claro e x-dark no escuro.
  # Fonte dos valores: mockups/paleta-tipografia.html, variação A2 (contraste WCAG 2.x medido sobre {colors.card}).
  background: '#ffffff'
  background-dark: '#121113'
  foreground: '#111827'
  foreground-dark: '#c1c1c1'
  card: '#ffffff'
  card-dark: '#121212'
  card-foreground: '#111827'
  card-foreground-dark: '#c1c1c1'
  popover: '#ffffff'
  popover-dark: '#121113'
  popover-foreground: '#111827'
  popover-foreground-dark: '#c1c1c1'
  muted: '#f3f4f6'
  muted-dark: '#222222'
  muted-foreground: '#6b7280'
  muted-foreground-dark: '#888888'
  border: '#e5e7eb'
  border-dark: '#222222'
  # input é separado de border: contorno de controle editável precisa de ≥ 3:1 (WCAG 1.4.11).
  input: '#8b8f97'
  input-dark: '#666666'
  ring: '#047745'
  ring-dark: '#4ade80'
  # Fundo de linha em hover, foco ou destaque. Texto sobre ele: foreground, muted-foreground, negative ou warning (todos ≥ 4,5:1).
  row-highlight: '#f9fafb'
  row-highlight-dark: '#1e1e1e'
  primary: '#72e3ad'
  primary-dark: '#006239'
  primary-foreground: '#1e2723'
  primary-foreground-dark: '#dde8e3'
  secondary: '#eeeeee'
  secondary-dark: '#333333'
  secondary-foreground: '#111827'
  secondary-foreground-dark: '#c1c1c1'
  accent: '#eeeeee'
  accent-dark: '#333333'
  accent-foreground: '#111827'
  accent-foreground-dark: '#c1c1c1'
  positive: '#047745'
  positive-dark: '#4ade80'
  negative: '#c51e21'
  negative-dark: '#fb605c'
  destructive: '#c51e21'
  destructive-dark: '#fb605c'
  destructive-foreground: '#ffffff'
  destructive-foreground-dark: '#121113'
  warning: '#a6501a'
  warning-dot: '#d87943'
  warning-dark: '#e78a53'
  warning-dot-dark: '#e78a53'
  # Fundos tingidos (cor a 10% no claro / 14% no escuro, sobre {colors.card}), já resolvidos em hex.
  positive-tint: '#e6f1ec'
  positive-tint-dark: '#1a2f21'
  negative-tint: '#f9e8e9'
  negative-tint-dark: '#331d1c'
  warning-tint: '#f6eee8'
  warning-tint-dark: '#30231b'
  sidebar: '#f3f4f6'
  sidebar-dark: '#121212'
  sidebar-foreground: '#111827'
  sidebar-foreground-dark: '#c1c1c1'
  sidebar-primary: '#72e3ad'
  sidebar-primary-dark: '#006239'
  sidebar-primary-foreground: '#1e2723'
  sidebar-primary-foreground-dark: '#dde8e3'
  sidebar-accent: '#ffffff'
  sidebar-accent-dark: '#333333'
  sidebar-accent-foreground: '#111827'
  sidebar-accent-foreground-dark: '#c1c1c1'
  sidebar-border: '#e5e7eb'
  sidebar-border-dark: '#222222'
  sidebar-ring: '#047745'
  sidebar-ring-dark: '#4ade80'
  chart-1: '#047745'
  chart-1-dark: '#4ade80'
  chart-2: '#6b7280'
  chart-2-dark: '#888888'
  chart-3: '#8f8f8f'
  chart-3-dark: '#636363'
typography:
  # B1: interface em sans geométrica; todo número em mono com tabular-nums (font-variant-numeric: tabular-nums).
  page-title:
    fontFamily: "Geist, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  section-title:
    fontFamily: "Geist, Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1.4'
  body:
    fontFamily: "Geist, Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: "Geist, Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.45'
  label:
    fontFamily: "Geist, Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.3'
    letterSpacing: 0.05em
  caption:
    fontFamily: "Geist, Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.4'
  num-display:
    fontFamily: "'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  num-lg:
    fontFamily: "'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: 16px
    fontWeight: '600'
    lineHeight: '1.4'
  num-body:
    fontFamily: "'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  num-table:
    fontFamily: "'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.45'
  tag:
    # Minúscula, sem text-transform. 12px é o mínimo para rótulo de estado.
    fontFamily: "'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.5'
    letterSpacing: 0.02em
rounded:
  # Base --radius = 0.75rem (darkmatter). Escala no padrão shadcn: sm = base−4px, md = base−2px, lg = base, xl = base+4px.
  xs: 4px
  sm: 8px
  md: 10px
  lg: 12px
  xl: 16px
  full: 9999px
spacing:
  # Escala Tailwind (base 4px) + tokens nomeados. Postura arejada: o respiro vem do espaço, não de bordas.
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 20px
  '6': 24px
  '8': 32px
  '10': 40px
  '12': 48px
  page-gutter: 32px
  section-gap: 24px
  card-padding: 16px
  card-gap: 12px
  table-cell-x: 16px
  table-cell-y: 8px
  table-cell-y-dense: 6px
  table-annotation-slot: 40px
  sidebar-width: 240px
  topbar-height: 56px
  content-max: 1440px
  viewport-target: 1280px
  viewport-floor: 1024px
  drawer-width: 560px
  drawer-width-wide: 'min(1040px, 100vw - 48px)'
components:
  sidebar:
    background: '{colors.sidebar}'
    foreground: '{colors.sidebar-foreground}'
    border: '{colors.sidebar-border}'
    item-active-background: '{colors.sidebar-accent}'
    item-active-indicator: '{colors.positive}'
    width: '{spacing.sidebar-width}'
  top-bar:
    background: '{colors.background}'
    border: '{colors.border}'
    height: '{spacing.topbar-height}'
  period-selector:
    background: '{colors.background}'
    border: '{colors.input}'
    value: '{typography.num-body}'
    radius: '{rounded.md}'
  alerts-bell:
    foreground: '{colors.muted-foreground}'
    count-background: '{colors.secondary}'
    count-foreground: '{colors.secondary-foreground}'
    count-font: '{typography.tag}'
  alerts-center:
    background: '{colors.popover}'
    width: '{spacing.drawer-width}'
  theme-switch:
    border: '{colors.input}'
    foreground: '{colors.muted-foreground}'
    radius: '{rounded.md}'
  kpi-card:
    background: '{colors.card}'
    border: '{colors.border}'
    radius: '{rounded.lg}'
    padding: '{spacing.card-padding}'
    label: '{typography.label}'
    label-color: '{colors.muted-foreground}'
    value: '{typography.num-display}'
    value-color: '{colors.card-foreground}'
  alert-item:
    border-top: '{colors.border}'
    dot-warning: '{colors.warning-dot}'
    dot-divergence: '{colors.negative}'
    tag-font: '{typography.tag}'
    tag-warning: '{colors.warning}'
    tag-warning-background: '{colors.warning-tint}'
    tag-divergence: '{colors.negative}'
    tag-divergence-background: '{colors.negative-tint}'
    tag-radius: '{rounded.xs}'
    action-color: '{colors.positive}'
  data-table:
    background: '{colors.card}'
    header-background: '{colors.muted}'
    header-text: '{colors.foreground}'
    header-font: '{typography.label}'
    row-border: '{colors.border}'
    row-hover: '{colors.row-highlight}'
    row-focus: '{colors.row-highlight}'
    cell-font: '{typography.body-sm}'
    number-font: '{typography.num-table}'
    fontVariantNumeric: tabular-nums
    cell-padding-x: '{spacing.table-cell-x}'
    cell-padding-y: '{spacing.table-cell-y}'
    annotation-slot: '{spacing.table-annotation-slot}'
    total-background: '{colors.muted}'
  change-pill:
    font: '{typography.num-table}'
    positive-text: '{colors.positive}'
    positive-background: '{colors.positive-tint}'
    negative-text: '{colors.negative}'
    negative-background: '{colors.negative-tint}'
    radius: '{rounded.xs}'
  status-badge:
    font: '{typography.tag}'
    background: '{colors.secondary}'
    foreground: '{colors.secondary-foreground}'
    background-warning: '{colors.warning-tint}'
    foreground-warning: '{colors.warning}'
    background-divergence: '{colors.negative-tint}'
    foreground-divergence: '{colors.negative}'
    radius: '{rounded.full}'
  data-stamp:
    font: '{typography.caption}'
    color: '{colors.muted-foreground}'
    stale-dot: '{colors.warning-dot}'
  progress-bar:
    track: '{colors.muted}'
    track-outline: '{colors.input}'
    realized: '{colors.positive}'
    in-transit: '{colors.positive}'
    segment-gap: '{colors.card}'
    height: '{spacing.2}'
    radius: '{rounded.full}'
  contribution-summary:
    background: '{colors.card}'
    border: '{colors.border}'
    radius: '{rounded.lg}'
    planned-font: '{typography.num-lg}'
    value-font: '{typography.num-body}'
  fixed-costs-summary:
    background: '{colors.card}'
    border: '{colors.border}'
    radius: '{rounded.lg}'
    row-font: '{typography.body-sm}'
    value-font: '{typography.num-table}'
  button-primary:
    background: '{colors.primary}'
    foreground: '{colors.primary-foreground}'
    radius: '{rounded.md}'
  button-secondary:
    background: '{colors.secondary}'
    foreground: '{colors.secondary-foreground}'
    border: '{colors.border}'
    radius: '{rounded.md}'
  button-ghost:
    background: transparent
    foreground: '{colors.foreground}'
    border: '{colors.input}'
    radius: '{rounded.md}'
  button-destructive:
    background: '{colors.destructive}'
    foreground: '{colors.destructive-foreground}'
    radius: '{rounded.md}'
  tabs:
    foreground: '{colors.muted-foreground}'
    active-foreground: '{colors.foreground}'
    active-indicator: '{colors.positive}'
  import-hub:
    background: '{colors.popover}'
    width: '{spacing.drawer-width}'
    dropzone-border: '{colors.input}'
    dropzone-radius: '{rounded.lg}'
  transaction-review:
    background: '{colors.popover}'
    width: '{spacing.drawer-width-wide}'
    row-focused: '{colors.row-highlight}'
    checkbox-border: '{colors.input}'
    checkbox-unchecked-background: '{colors.background}'
    checkbox-checked: '{colors.primary}'
    origin-tag-font: '{typography.tag}'
  category-combobox:
    background: '{colors.popover}'
    border: '{colors.input}'
    radius: '{rounded.md}'
    empty-border: '{colors.warning}'
  rule-proposal:
    background: '{colors.muted}'
    foreground: '{colors.foreground}'
    radius: '{rounded.md}'
    font: '{typography.body-sm}'
  allocation-distribution:
    background: '{colors.card}'
    locked-icon: '{colors.foreground}'
    out-of-band: '{colors.warning}'
    number-font: '{typography.num-table}'
    planned-input-font: '{typography.num-lg}'
    planned-input-border: '{colors.input}'
  month-close:
    closed-badge-background: '{colors.secondary}'
    adjustment-tag: '{colors.warning}'
  chart-net-worth:
    series: '{colors.chart-1}'
    reference: '{colors.chart-3}'
    grid: '{colors.border}'
    axis-font: '{typography.caption}'
  chart-spending:
    current: '{colors.chart-2}'
    previous-outline: '{colors.chart-3}'
    grid: '{colors.border}'
  chart-contribution:
    planned: '{colors.chart-2}'
    realized: '{colors.chart-1}'
    grid: '{colors.border}'
  empty-state:
    title: '{typography.section-title}'
    body: '{typography.body}'
    color: '{colors.muted-foreground}'
  skeleton:
    background: '{colors.muted}'
    radius: '{rounded.sm}'
  confirm-dialog:
    background: '{colors.popover}'
    radius: '{rounded.xl}'
  sources-block:
    background: '{colors.card}'
    border: '{colors.border}'
    radius: '{rounded.lg}'
    name-font: '{typography.body-sm}'
    date-font: '{typography.num-table}'
    stale-dot: '{colors.warning-dot}'
    row-border: '{colors.border}'
  reading-selector:
    background: '{colors.muted}'
    foreground: '{colors.foreground}'
    active-background: '{colors.background}'
    active-foreground: '{colors.foreground}'
    font: '{typography.body-sm}'
    radius: '{rounded.md}'
  side-form:
    background: '{colors.popover}'
    width: '{spacing.drawer-width}'
    field-border: '{colors.input}'
    error-text: '{colors.negative}'
    footer-border: '{colors.border}'
  toast:
    # Herdado do Sonner (shadcn) sem customização; listado para o theme-showcase.
    background: '{colors.popover}'
    foreground: '{colors.popover-foreground}'
    border: '{colors.border}'
    radius: '{rounded.md}'
  recovery-wizard:
    background: '{colors.card}'
    border: '{colors.border}'
    radius: '{rounded.lg}'
    step-font: '{typography.label}'
    month-font: '{typography.num-body}'
    step-done: '{colors.foreground}'
    step-current: '{colors.foreground}'
    step-pending: '{colors.muted-foreground}'
  close-checklist:
    item-font: '{typography.body-sm}'
    item-ok: '{colors.foreground}'
    item-pending-dot: '{colors.warning-dot}'
  broker-card:
    background: '{colors.card}'
    border: '{colors.border}'
    radius: '{rounded.lg}'
    padding: '{spacing.card-padding}'
    label: '{typography.label}'
    value: '{typography.num-body}'
    input-border: '{colors.input}'
  fixed-costs-list:
    # Base: data-table (Tabela de dados).
    match-font: '{typography.body-sm}'
    candidate-border: '{colors.warning}'
  budget-ledger:
    background: '{colors.card}'
    operator-font: '{typography.num-body}'
    operator-color: '{colors.muted-foreground}'
    value-font: '{typography.num-body}'
    total-font: '{typography.num-lg}'
    total-rule: '{colors.foreground}'
    negative: '{colors.negative}'
    input-border: '{colors.input}'
  import-history:
    row-font: '{typography.body-sm}'
    number-font: '{typography.num-table}'
    row-border: '{colors.border}'
---

# DESIGN — Goodies v2

**Mockups aprovados:** `mockups/` (Painel, Revisão de transações, Aportes, Orçamento; paleta e tipografia). Em conflito, os spines prevalecem.

## Brand & Style

O Goodies é um **terminal de trader, porém arejado**: sóbrio, técnico e calmo. Os números ficam em primeiro plano e a interface se cala ao redor deles. Não é planilha nem app de banco, e não tenta empolgar. Três apoios visuais:

- **Neutros quase pretos e quase brancos** (tweakcn *darkmatter*) carregam a estrutura.
- **Um verde** (tweakcn *supabase*) significa ação e ganho.
- **Um laranja queimado** aparece só para dizer "isto pede ação".

Mais números que gráficos; poucas bordas, espaço generoso.

**Fundação:** shadcn/ui (estilo new-york) + Radix + Tailwind v4 sobre o Next.js App Router. Este arquivo especifica só o **delta**; o que não está aqui (Dialog, Sheet, Popover, Command, Tooltip, Checkbox, DropdownMenu, Skeleton, Sonner) usa o shadcn sem customização. O tema segue o sistema operacional, com **Switch de tema** manual (sistema / claro / escuro). Os dois modos são de primeira classe.

**Do grupo-natus, só o rigor, não a estética:**

- **Só tokens semânticos.** Componente nunca usa cor crua.
- **Teste "no raw color".** Falha o build se aparecer hex, `rgb()`, `hsl()` ou `oklch()` fora do arquivo de tokens (`web/app/globals.css`), ou classe de paleta do Tailwind (`text-red-500`, `bg-emerald-*` e afins) em componente.
- **Página theme-showcase** (rota `/dev/tema`, só em ambiente local): referência viva com todos os tokens e componentes, em todos os estados, no claro e no escuro lado a lado.

## Colors

→ Referência visual: [`mockups/paleta-tipografia.html`](mockups/paleta-tipografia.html), variação **A2** (paleta) + **B1** (tipografia). Cada `{colors.x}` resolve para `x` no claro e `x-dark` no escuro.

- **Neutros (darkmatter).** No escuro, fundo e card quase se igualam (#121113 / #121212): a separação vem de `{colors.border}` e do espaço, não de tom. `{colors.secondary}` e `{colors.accent}` usam o `--accent` do darkmatter (#eeeeee / #333333), porque o `--secondary` original é um teal que brigaria com o verde.
- **Contorno de controle.** `{colors.input}` (sempre ≥ 3:1) é separado de `{colors.border}`: contorna input, Combobox, checkbox, Seletor de período e trilho da Barra de progresso. `{colors.border}` fica discreto, só para cards e divisórias.
- **Linha destacada.** `{colors.row-highlight}` é o fundo de hover, foco e destaque de linha em tabela. Nunca `{colors.accent}` em linha (ver pares proibidos).
- **Verde (supabase): ação e positivo.** `{colors.primary}` é o fundo de botão primário. `{colors.positive}` = `{colors.ring}` é o verde de texto e de elemento gráfico: valor positivo, foco, aba ativa, preenchimento de progresso e `{colors.chart-1}`. No claro, #72e3ad dá ~1,5:1 sobre branco: só fundo de botão; texto e foco usam o derivado #047745. No escuro, barra de progresso e aba ativa usam `{colors.positive}`, não `{colors.primary}` (#006239 sobre #222 tem contraste baixo).
- **Vermelho: negativo.** `{colors.negative}` marca valor negativo e divergência de conferência. `{colors.destructive}` é o mesmo vermelho em ação destrutiva, no lugar do `--destructive` do darkmatter (teal no escuro, sem a ideia de perda).
- **Laranja queimado: só avisos.** `{colors.warning}` é o texto da tag de aviso (no claro, #a6501a: o original #d87943 dá 3,12:1 e não serve como texto). `{colors.warning-dot}` é o ponto ou realce.
- **Tints.** `{colors.positive-tint}`, `{colors.negative-tint}` e `{colors.warning-tint}` são o fundo do Selo de variação, das tags de aviso e das variantes aviso/divergência do Selo de estado (a cor a 10% no claro e 14% no escuro, resolvida sobre `{colors.card}`).
- **Gráficos: três tons, sem arco-íris.** `{colors.chart-1}` (verde) = série principal ou realizada; `{colors.chart-2}` (neutro médio) = série corrente neutra (gastos) ou planejada; `{colors.chart-3}` (neutro claro) = referência (período anterior, média 12m, aplicado). `[ASSUMPTION: mapeamento das séries nos três gráficos]`
- **Barra lateral.** `{colors.sidebar}` é cinza-claro no claro e igual ao card no escuro. `sidebar-primary*` espelha `primary*`; `sidebar-ring` espelha `ring`.

**Migração de `web/app/globals.css`:** `--gain` → `--positive`; `--loss` → `--negative`; `--warning` com os novos valores; `--accent` índigo removido. O `@theme inline` expõe os tokens shadcn + `positive`, `negative`, `warning`, `warning-dot`, `*-tint`, `row-highlight` e `chart-1..3`.

**Contraste (WCAG 2.x, sobre `{colors.card}` salvo indicação):**

| Par | Claro | Escuro | Alvo |
|---|---|---|---|
| foreground / card | 17,74:1 | 10,41:1 | ≥ 4,5 |
| muted-foreground / card | 4,83:1 | 5,29:1 | ≥ 4,5 |
| primary-foreground / primary | 9,71:1 | 5,96:1 | ≥ 4,5 |
| positive / card | 5,65:1 | 10,75:1 | ≥ 4,5 |
| negative / card | 5,85:1 | 6,20:1 | ≥ 4,5 |
| warning / card | 5,56:1 | 7,28:1 | ≥ 4,5 |
| positive / positive-tint (Selo de variação) | 4,87:1 | 8,18:1 | ≥ 4,5 |
| negative / negative-tint (Selo de variação, Selo de estado "divergente", tag de divergência) | 4,95:1 | 5,20:1 | ≥ 4,5 |
| warning / warning-tint (Selo de estado de aviso, tag de aviso) | 4,84:1 | 5,90:1 | ≥ 4,5 |
| secondary-foreground / secondary (Selo de estado neutro) | 15,29:1 | 7,02:1 | ≥ 4,5 |
| foreground · muted-foreground / row-highlight | 16,98 · 4,63:1 | 9,26 · 4,70:1 | ≥ 4,5 |
| warning · negative / row-highlight | 5,31 · 5,61:1 | 6,48 · 5,50:1 | ≥ 4,5 |
| tag tingida em linha destacada (warning · negative) | 4,63 · 4,77:1 | 5,16 · 4,57:1 | ≥ 4,5 |
| foreground / muted (cabeçalho de tabela, Proposta de regra) | 16,12:1 | 8,84:1 | ≥ 4,5 |
| destructive-foreground / destructive | 5,86:1 | 6,21:1 | ≥ 4,5 |
| input / card · background (contorno de controle, checkbox, trilho) | 3,24:1 | 3,26 · 3,28:1 | ≥ 3 (não-texto) |
| positive / muted (trechos da Barra de progresso sobre o trilho) | 5,12:1 | 9,13:1 | ≥ 3 (não-texto) |
| ring / background | 5,63:1 | 10,8:1 | ≥ 3 (não-texto) |
| warning-dot / card | 3,12:1 | 7,28:1 | ≥ 3 (só gráfico) |
| chart-1 · chart-2 · chart-3 / card | 5,65 · 4,83 · 3,23:1 | 10,75 · 5,29 · 3,12:1 | ≥ 3 (não-texto) |

**Pares proibidos para texto:**

- `{colors.muted-foreground}` sobre `{colors.muted}` (4,39:1 claro; 4,49:1 escuro) ou sobre `{colors.sidebar}` no claro (4,39:1). Por isso cabeçalho de tabela, opção inativa de grupo segmentado, item inativo da barra lateral e texto da Proposta de regra usam `{colors.foreground}` / `{colors.sidebar-foreground}`.
- `{colors.muted-foreground}` e `{colors.warning}` sobre `{colors.accent}` (4,17 / 3,56:1 e 4,19 / 3,93:1). Linha destacada usa `{colors.row-highlight}`.
- `{colors.warning}` e `{colors.negative}` sobre `{colors.secondary}` (4,78 / 4,91:1 e 5,05 / 4,17:1). Selo de estado de aviso ou divergência usa o tint, nunca `secondary`.
- Controle editável sobre `{colors.row-highlight}`: `{colors.input}` dá 2,90:1 no escuro. O controle mantém fundo próprio (`{colors.popover}` ou `{colors.background}`) e o contorno se mede contra ele.

## Typography

→ Referência visual: [`mockups/paleta-tipografia.html`](mockups/paleta-tipografia.html), variação **B1**: **sans para falar, mono para contar.**

- **UI em Geist (fallback Inter):** rótulos, títulos e prosa.
- **Todo número em Geist Mono (fallback JetBrains Mono)**, sempre com `font-variant-numeric: tabular-nums`: valores, percentuais, datas em tabela e contadores. As colunas alinham pela vírgula.

| Papel | Token | Uso |
|---|---|---|
| Título da página | `{typography.page-title}` | Nome da área no topo do conteúdo |
| Título de seção | `{typography.section-title}` | Cabeçalho de card e de tabela |
| Corpo | `{typography.body}` / `{typography.body-sm}` | Prosa, células de texto (13px em tabela) |
| Rótulo | `{typography.label}` | Rótulo de KPI e cabeçalho de coluna, em CAIXA ALTA |
| Legenda | `{typography.caption}` | Carimbo de data, eixos, notas |
| Número destaque | `{typography.num-display}` | Valor do Cartão KPI |
| Número de ênfase | `{typography.num-lg}` | Aporte planejado (resumo e input), linhas "=" da Conta do orçamento |
| Número corrente | `{typography.num-body}` / `{typography.num-table}` | Valores em texto e em tabela |
| Tag | `{typography.tag}` | Tags de aviso e de origem, Selo de estado, contadores |

Regras:

- Números à direita em tabela; moeda sempre completa ("R$ 68.695,66", nunca "68,7 mil").
- Pesos 400 e 600; 500 só em `{typography.label}` e nos números de linha de grupo. Sem itálico.
- **Caixa:** CAIXA ALTA só em `{typography.label}` (via `text-transform`). Tags e Selos de estado em minúscula, escritos assim, sem `text-transform` ("divergente", "a caminho", "sem sugestão"). Datas e meses nunca em caixa alta: o mês fica fora do rótulo ("Aporte planejado", não "APORTE PLANEJADO DE OUT/2026").
- Nenhum tamanho fora da escala: ênfase intermediária é `{typography.num-lg}`.

## Layout & Spacing

**Desktop-first.** Barra lateral de `{spacing.sidebar-width}` à esquerda; Barra superior de `{spacing.topbar-height}`; conteúdo com margem `{spacing.page-gutter}` e largura máxima `{spacing.content-max}`.

**Faixas de largura:**

- **≥ `{spacing.viewport-target}` (1280px): alvo.** Tudo na grade abaixo, sem rolagem horizontal.
- **1024–1279px: degradação graciosa.** A fileira de 4 Cartões KPI vira 2×2 (container query: conteúdo abaixo de ~1040px). Pares lado a lado empilham quando cada metade fica estreita demais para os números.
- **< `{spacing.viewport-floor}` (1024px), inclusive zoom de 200%: reflui para uma coluna.** Grades e pares empilham; painéis laterais ocupam a largura toda. A barra lateral dá lugar à **navegação inferior** (as 4 áreas, ao alcance do polegar, com a área segura do iPhone) e o Importar vai para a barra superior.
- **< 640px — celular (alvo desde a v2.2):** margem lateral de 16px; texto de corpo pequeno e número de tabela sobem a 14px; campos em 16px (o iOS não amplia ao focar). A Tabela de dados vira **cartões** (título, valor ao lado, metadados sob o título, demais colunas como rótulo/valor); Posições, Objetivos e Classes do aporte têm cartão próprio; filtros e seções longas ficam recolhidos (`Section`). Item de grade nunca cresce além da coluna (`min-width: 0`): a tabela rola dentro do card.

**Tabelas nunca cortam.** Se não cabem, rolam na horizontal dentro do próprio card, com pista visível (sombra/fade na borda com conteúdo escondido) e a primeira coluna fixa. No modo Resumo, colunas de baixa prioridade (Alvo, Prazo, % do consumido) saem antes de rolar. Valor monetário nunca é truncado nem quebrado.

**Ritmo arejado:** `{spacing.section-gap}` entre blocos, `{spacing.card-gap}` entre cards da mesma grade, `{spacing.card-padding}` dentro dos cards. Tabelas têm duas densidades: **Resumo** (`{spacing.table-cell-y}`) e **Detalhado**, tudo à vista (`{spacing.table-cell-y-dense}`). A fonte continua `{typography.body-sm}`: densidade se ganha no padding, nunca diminuindo a fonte.

**Grade do Painel principal** ([`mockups/key-painel.html`](mockups/key-painel.html)); a ordem de leitura é a ordem de prioridade:

1. Linha de aviso (até 3) + "Ver todos ({n})", largura total. O Sino de avisos conta todos.
2. **Saldo em caixa** (o saldo do extrato, conferido ao centavo) | **Fluxo do mês** (barra das entradas: custos fixos, aporte, dívidas, gastos, sobra; frase "Sobram/Faltam R$ x"), 2/5 e 3/5 — desde a v2.2, no lugar de "Disponível para consumo × restante".
3. Cartões KPI **Resultado do mês** | **Patrimônio** | **Resultado dos investimentos** | **Rentabilidade nominal** | **Rentabilidade real**, 5 colunas (2 abaixo de 1280px). A real usa o último IPCA publicado para o mês que ainda não saiu, marcado como estimado.
4. **Resumo do aporte** | **Resumo de custos fixos**, metade cada, alinhados ao topo (sem esticar para a altura do vizinho).
5. **Bloco Fontes**, largura total, recolhido.

O Assistente de recuperação, quando existe, fica acima de tudo. Sem gráfico no Painel. Tabelas de área (Transações, Posições, Distribuição do aporte, Conciliação) ocupam a largura total; blocos-resumo (Resumo de custos fixos, Consumido por grupo ao lado da Conta do orçamento) podem ocupar meia largura.

**Painéis laterais:** Hub de import, Central de avisos e Formulário em painel lateral ocupam `{spacing.drawer-width}` (560px); a Revisão de transações ocupa `{spacing.drawer-width-wide}` = `min(1040px, 100vw − 48px)`, que a mantém responsiva abaixo de 1280px.

## Elevation & Depth

A hierarquia vem do espaço, da tipografia e de bordas de 1px em `{colors.border}`, não de sombra.

- **Cards:** sem sombra no escuro; no claro, só o `shadow-sm` do darkmatter (`0 1px 4px hsl(0 0% 0% / .05)`).
- **Camadas flutuantes** (Popover, Combobox, Painel lateral, Diálogo): `{colors.popover}` com a sombra padrão do shadcn. Painéis laterais e diálogos escurecem o fundo com o overlay padrão.
- **Pilha:** no máximo um painel lateral + um diálogo por cima.
- Nada de glassmorphism, gradiente ou brilho.

## Shapes

Base de raio **0,75rem** (darkmatter), confirmada nos mockups aprovados.

| Token | Valor | Uso |
|---|---|---|
| `{rounded.xs}` | 4px | Tags e Selo de variação |
| `{rounded.sm}` | 8px | Checkbox e Esqueleto |
| `{rounded.md}` | 10px | Botões, inputs, Combobox e Switch de tema |
| `{rounded.lg}` | 12px | Cards e dropzone |
| `{rounded.xl}` | 16px | Diálogos |
| `{rounded.full}` | 9999px | Só Selo de estado e trilho da Barra de progresso |

Painéis laterais têm canto reto no lado preso à tela.

## Components

Base no shadcn; a coluna "Visual" registra só o que muda. Comportamento, conteúdo e vocabulário de selos e tags: `EXPERIENCE.md` › Component Patterns, com os mesmos nomes.

| Componente | Base shadcn | Visual |
|---|---|---|
| **Barra lateral** (`sidebar`) | Sidebar | Marca "goodies" em mono com quadrado `{colors.positive}`. Botão Importar fixo em `button-primary`. Item ativo com fundo `{colors.sidebar-accent}` e marcador vertical `{colors.positive}`. |
| **Barra superior** (`top-bar`) | — | Seletor de período à esquerda; Sino de avisos e Switch de tema à direita. Borda inferior `{colors.border}`. |
| **Seletor de período** (`period-selector`) | Popover + Button | Mês em mono, minúsculo ("out/2026"), setas ‹ › e Selo de estado ("aberto", "fechado" ou "ajuste"). No popover, meses sem dados ou futuros em `{colors.muted-foreground}`, desabilitados. |
| **Seletor de leitura** (`reading-selector`) | ToggleGroup | Grupo segmentado no cabeçalho da aba, à direita do título. Trilho `{colors.muted}`; inativas em `{colors.foreground}`; ativa em `{colors.background}` 600, nunca verde. O alternador Resumo/Detalhado da Tabela de dados usa o mesmo visual. |
| **Sino de avisos** (`alerts-bell`) | Button ghost | Ícone de sino com contador em `{typography.tag}`; sem contador quando zero. Sem vermelho. |
| **Central de avisos** (`alerts-center`) | Sheet (direita) | Lista de Linha de aviso agrupada por severidade; cabeçalho com o total. |
| **Switch de tema** (`theme-switch`) | DropdownMenu | Ícone meio-círculo; opções Sistema / Claro / Escuro. |
| **Cartão KPI** (`kpi-card`) | Card | Rótulo `{typography.label}` em `{colors.muted-foreground}`; valor `{typography.num-display}`; linha de apoio (variação ou nota) + Carimbo de data. O valor só fica colorido quando o sinal é o próprio dado (Resultado do mês, Resultado dos investimentos), sempre com sinal e seta. Rentabilidade nominal e real em cartões separados, com "a.a." em `{typography.caption}`. |
| **Linha de aviso** (`alert-item`) | — | Ponto com halo + tag de severidade + mensagem + ação como link `{colors.positive}`. A tag ocupa slot de largura fixa (a da tag mais longa), para todas as mensagens começarem no mesmo x. Severidade **divergência** (saldo divergente, posição divergente da origem, caixa em corretora divergente da conferência): texto `{colors.negative}` sobre `{colors.negative-tint}`. Os demais tipos são **aviso**: texto `{colors.warning}` sobre `{colors.warning-tint}`, ponto `{colors.warning-dot}`. Variante compacta (sem borda, recuada) dentro de tabelas e resumos. |
| **Bloco Fontes** (`sources-block`) | Card + Table | Tabela compacta em largura total: fonte, tipo (OFX, xlsx, automático), atualizado até (Carimbo de data) e saldo. Na conta Nubank PF, o saldo traz Selo de estado "conferido" ou "divergente" seguido do valor ("divergente · R$ 37,20"). Mesmo visual no Painel e no topo do Hub de import. |
| **Tabela de dados** (`data-table`) | Table + TanStack | Cabeçalho em `{colors.muted}` com texto `{colors.foreground}`; linhas separadas por `{colors.border}`; hover e foco em `{colors.row-highlight}`; números à direita em mono. **Linha de grupo:** 600 só no rótulo (com chevron); números em 500. **Total:** 600 + fundo `{colors.muted}`. **Anotações** (desvio em p.p., "piso", cadeado) em coluna própria ou num slot de `{spacing.table-annotation-slot}` depois do número; o número sempre encosta na mesma borda. Alternador Resumo/Detalhado no cabeçalho. |
| **Selo de variação** (`change-pill`) | Badge | Seta + sinal + valor sobre o tint da própria cor: "▲ +R$ 682,10" em `{colors.positive}` sobre `{colors.positive-tint}`; "▼ −R$ 163,80" em `{colors.negative}` sobre `{colors.negative-tint}`. Alinhado à direita, com a mesma largura mínima em toda a coluna. |
| **Selo de estado** (`status-badge`) | Badge | Pílula `{rounded.full}` em `{typography.tag}`, minúscula. Tons: **neutro** `{colors.secondary-foreground}` sobre `{colors.secondary}`; **aviso** `{colors.warning}` sobre `{colors.warning-tint}`; **divergência** `{colors.negative}` sobre `{colors.negative-tint}`. Check neutro opcional à esquerda em "conferido" e "pago". Nunca verde: estado bom não é ganho. |
| **Carimbo de data** (`data-stamp`) | — | "até 14/10/2026" em `{typography.caption}`, `{colors.muted-foreground}`; defasado, ponto `{colors.warning-dot}` à esquerda. |
| **Barra de progresso** (`progress-bar`) | Progress | Trilho `{colors.muted}` de `{spacing.2}` com contorno interno de 1px `{colors.input}` (o fim de 100% aparece). Três trechos, nesta ordem: **realizado em ativo** (sólido `{colors.positive}`), **a caminho** (hachura diagonal `{colors.positive}`, porque faz parte do realizado total) e **pendente** (trilho vazio), separados por 1px `{colors.card}`. A legenda repete as amostras com os mesmos rótulos. |
| **Resumo do aporte** (`contribution-summary`) | Card | Cabeçalho "Aporte do mês" + link "Ver aportes". Planejado em `{typography.num-lg}`; linha do realizado; Barra de progresso com legenda; linha "a caminho" com Selo de estado; Linha de aviso compacta de classes fora da banda, quando houver. Rodapé: "% realizado" + Carimbo de data. |
| **Resumo de custos fixos** (`fixed-costs-summary`) | Card | Cabeçalho "Custos fixos" + "pago X de Y" + link "Ver custos fixos". Linhas com nome, data em `{typography.caption}`, valor em mono e Selo de estado; pagos recolhidos numa linha. Rodapé: total a pagar + Carimbo de data. |
| **Botão** (`button-primary` / `-secondary` / `-ghost` / `-destructive`) | Button | Primário verde, um por região. Destrutivo só em "Desfazer" (Histórico de imports). Ação terciária dentro de faixa ou linha é link (`{colors.positive}`, sublinhado), não botão. |
| **Abas** (`tabs`) | Tabs (variante linha) | Sublinhado de 2px em `{colors.positive}` na aba ativa; inativas em `{colors.muted-foreground}`. |
| **Toast** (`toast`) | Sonner | Sem customização: `{colors.popover}`, sem ícone colorido nem botão. |
| **Hub de import** (`import-hub`) | Sheet (direita) | Bloco Fontes no topo + dropzone tracejada `{colors.input}` + prévia do lote em Tabela de dados + Histórico de imports no rodapé. |
| **Histórico de imports** (`import-history`) | Table | Lista compacta de lotes, data e contagens em mono. Só a linha do último lote tem o `button-destructive` "Desfazer". |
| **Revisão de transações** (`transaction-review`) | Sheet (direita, larga) | Tabela de dados com coluna de checkbox (contorno `{colors.input}`; desmarcado com fundo `{colors.background}`; marcado em `{colors.primary}`), Combobox de categoria inline, tag de origem e rodapé fixo com o total e "Confirmar". Linha marcada não muda de fundo (o checkbox carrega o estado). Linha focada em `{colors.row-highlight}` com anel `{colors.ring}`. [`mockups/key-revisao.html`](mockups/key-revisao.html) |
| **Combobox de categoria** (`category-combobox`) | Command em Popover | Opções "Grupo › Subcategoria". Contorno `{colors.input}`; vazio ("sem sugestão") com borda `{colors.warning}`. |
| **Proposta de regra** (`rule-proposal`) | — (faixa inline) | Faixa `{colors.muted}` com texto `{colors.foreground}` sob a linha corrigida, recuada até a coluna de descrição: "Criar regra?" em 600, condição editável, número de transações afetadas e três ações (Criar regra em `button-secondary`; Ajustar condição e Agora não como links). |
| **Formulário em painel lateral** (`side-form`) | Sheet (direita) + Form | Título com o verbo ("Novo custo fixo"); campos em uma coluna, rótulo acima; erro sob o campo em `{colors.negative}`, com texto; rodapé fixo com borda `{colors.border}`, Salvar (`button-primary`) e Cancelar (`button-ghost`). |
| **Conta do orçamento** (`budget-ledger`) | Table | Conta vertical: operador (+ − =) em coluna própria, mono `{colors.muted-foreground}`, inclusive o "+" da primeira linha; valores em mono à direita. Linhas "=" com régua de 1px `{colors.foreground}` acima e valor em `{typography.num-lg}`. Dívidas do mês como input inline (contorno `{colors.input}`), texto do valor alinhado à borda da coluna. Disponível ou restante negativo em `{colors.negative}` com "−" e ▼; a nota explicativa em `{colors.muted-foreground}`. "Consumo financiado por resgate" abaixo, após `{spacing.section-gap}` e régua `{colors.border}`, em `{typography.body-sm}`, sem caixa própria. [`mockups/key-orcamento.html`](mockups/key-orcamento.html) |
| **Lista de custos fixos com casamento** (`fixed-costs-list`) | Tabela de dados | Colunas: custo, valor, vencimento, Selo de estado, transação casada, ações (em link). "2 candidatas" abre as opções como RadioGroup sob a linha, com borda `{colors.warning}` à esquerda. |
| **Distribuição do aporte** (`allocation-distribution`) | Tabela de dados | Acima, o input do aporte planejado (`{typography.num-lg}`, contorno `{colors.input}`). Objetivos (com Barra de progresso até o alvo) e classes (expansíveis para ativos) compartilham a grade das colunas Sugerido, Realizado e Pendente. Coluna própria "Desvio" (p.p.); fora da banda, desvio em `{colors.warning}` + Linha de aviso compacta. Cadeado `{colors.foreground}` e "piso" no slot de anotação. Rodapé de conciliação com operador em coluna, como a Conta do orçamento. [`mockups/key-aportes.html`](mockups/key-aportes.html) |
| **Cartão de corretora** (`broker-card`) | Card | Rótulos `{typography.label}` à esquerda, valores em mono à direita; "a caminho" com Selo de estado. Rodapé com Carimbo de data e o input "Saldo que vejo na corretora" (contorno `{colors.input}`); preenchido, mostra calculado × informado e o Selo de estado. Grade de 2 ou 3 colunas. |
| **Fechamento de mês** (`month-close`) | Card + Diálogo de confirmação | Lista do resumo a congelar; Selo de estado "fechado" / "ajuste". Reabrir mostra congelado × recalculado em Tabela de dados, diferença em Selo de variação. |
| **Checklist de fechamento** (`close-checklist`) | — (lista no AlertDialog) | Três itens: check neutro `{colors.foreground}` quando ok ou ponto `{colors.warning-dot}` quando pendente, sempre com texto ("1 aviso ativo"); link para resolver à direita. Check de tarefa nunca é verde. |
| **Assistente de recuperação** (`recovery-wizard`) | Card | Trilha horizontal dos meses em mono (jun/2026 … out/2026), cada um com Selo de estado; sob o mês atual, os 4 passos em `{typography.label}`: feito com check neutro `{colors.foreground}`, atual em `{colors.foreground}` 600, a fazer em `{colors.muted-foreground}`. Um único `button-primary`, no passo atual. |
| **Gráfico de patrimônio** (`chart-net-worth`) | Chart (Recharts) | Linha de 2px `{colors.chart-1}`; série "aplicado" tracejada em `{colors.chart-3}`; grade só horizontal; sem área preenchida. Os três gráficos têm "Ver como tabela" (`button-ghost`) no cabeçalho. |
| **Gráfico de gastos por categoria** (`chart-spending`) | Chart | Barras horizontais por grupo: período preenchido em `{colors.chart-2}`, anterior só com contorno de 1px `{colors.chart-3}` (diferença por forma, não só por tom), rótulo direto no fim da barra; média 12m como marcador vertical. Sem cor por categoria. |
| **Gráfico de aporte planejado × realizado** (`chart-contribution`) | Chart | Barras agrupadas por mês: planejado `{colors.chart-2}`, realizado `{colors.chart-1}`. |
| **Estado vazio** (`empty-state`) | — | Título `{typography.section-title}` + uma frase + no máximo uma ação. Sem ilustração. |
| **Esqueleto** (`skeleton`) | Skeleton | Mesma geometria do conteúdo final. |
| **Diálogo de confirmação** (`confirm-dialog`) | AlertDialog | Título com o verbo, resumo do efeito em números e botão com o verbo ("Fechar out/2026"). |

## Do's and Don'ts

| Faça | Não faça |
|---|---|
| Só tokens semânticos; rodar o teste "no raw color" | Hex, `oklch()` ou classe de paleta do Tailwind em componente |
| Laranja só para aviso | Laranja como destaque, marca ou categoria |
| Verde para ação e valor positivo | Verde decorativo, em ícone de seção ou em check de tarefa |
| Variação e resultado: "+" e ▲ em `{colors.positive}`, "−" e ▼ em `{colors.negative}`; transação e saldo: só o sinal | Cor como único sinal de positivo ou negativo |
| Números em mono tabular, à direita, completos; anotações em coluna ou slot próprio | "R$ 68,7 mil", "68.7k", número em sans, anotação colada ao número |
| Tags e selos escritos em minúscula | `text-transform: uppercase` em tag, selo, data ou mês |
| Gráficos neutros + um verde; **pizza (v2.2) só em tons do verde principal** (`--pie-1..8`, claro e escuro alternados), uma fatia por item, sempre com legenda de nome, % e valor | Cor por categoria, gradiente, pizza sem legenda |
| Separar com espaço e bordas de 1px | Sombras empilhadas, cards dentro de cards |
| Testar cada tela no claro e no escuro (theme-showcase) | Ajustar um modo e "ver depois" o outro |
| Herdar o shadcn quando não há motivo para mudar | Recriar Dialog, Sheet ou Combobox do zero |
| Deixar a estética da planilha para trás | Roxo, categorias coloridas, 16 abas soltas |
