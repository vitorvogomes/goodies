---
review: verify-r2
target: ../ARCHITECTURE-SPINE.md (revisão de 2026-10-18)
inputs: [review-adversary.md, review-reconcile-prd.md, review-reconcile-ux-adr.md, review-rubric.md, review-versions.md, ../.memlog.md]
date: '2026-10-18'
verdict: quase pronto (fechar 10 parciais + 5 novos no texto; nenhum exige decisão nova de produto)
---

# Verificação r2 — spine revisado

## Veredito

A revisão fecha todos os achados estruturais: dono da derivação de caixa, `goal_assets`,
`as_of` + histórico de preço, porta de status do mês, `broker_position_snapshots`,
`import_batch_files`, lotes legados, `Valued`, backup e versões. Ainda assim, **10 itens (14 dos 30 achados
críticos/altos, agrupando duplicatas) fecham só em parte**. A varredura nova achou **5 contradições introduzidas pela
própria revisão**: AD-8 capturando listas de fatos e prévias, snapshot × termos de `planning`, XIRR de período ×
patrimônio, idioma dos enums e desfazer × `categorization_events`. Cada uma deixa duas stories
corretas pela letra montando peças incompatíveis. Todas se fecham com texto no spine.

## 1. Fechamento dos achados críticos/altos

| Achado | Sev | Status | Onde fecha / o que falta |
| --- | --- | --- | --- |
| ADV P1 / PRD F2 / RUB F-1 — derivação caixa→ativos | C/H | **parcial** | AD-6 + AD-5 `on_batch_applied`. Falta quem apaga as derivadas no desfazer e em que ordem (§2.1) |
| ADV P2 — vínculo transação/objetivo→ativo | C | fechado | AD-6 resolver, AD-11 `goal_assets` em `planning` |
| ADV P3 — ao vivo de mês passado | C | **parcial** | AD-8 `as_of`, `asset_price_history`, vigência (AD-14), `dirty`. Falta o valor inicial quando o mês anterior está aberto (§2.2) |
| ADV P4 — período abaixo de `closing` | C | **parcial** | AD-8 roteia por `closing`, mas o mapa de capacidades ainda põe FR-15/16/20/21/22/28–31 nas engines baixas (§2.3) |
| ADV P5 / RUB F-5 — trimestre misto | H | **parcial** | AD-8 período. "Civil" contradiz o EXPERIENCE ("ano até ele"); falta `inicio`, truncamento, `source`/`as_of`/`stale` por período (§2.2) |
| ADV P6 — porta de status do mês | H | fechado | `MonthStatusPort` + `AlertContext` em `common` (barato: nomear os métodos, §4) |
| ADV P7 — `kind`/linhas sem categoria | H | **parcial** | AD-6 "a classificar" + recópia. Falta mudar o tipo do grupo e definir onde "a classificar" conta (§2.4) |
| ADV P8 — papéis | H | fechado | `categories.role` (barato: papel de subcategoria criada pelo usuário, §4) |
| ADV P9 — custo fixo × dívidas | H | **parcial** | AD-7 balde único + 1:1. Falta o algoritmo de desempate e a dupla contagem no `ensure_month_plan(retro)` (§2.5) |
| ADV P10 / PRD F14 / RUB F-9 — retroativo | H | **parcial** | AD-8 `close_retro` + `ensure_month_plan`. Falta o aporte planejado retro, a guarda de revisão e `origin` (§2.6) |
| ADV P11 — identidade do ativo | H | **parcial** | AD-11 `assets.id`/`key`/`price_ref`. Falta meta por ativo, alias de carteira e tipo de `dimension_id` (§2.7) |
| PRD F1 / UX C4 / RUB F-4 — consolidado B3 | H | fechado | `broker_position_snapshots` (Seed, AD-8, AD-13) |
| PRD F3 — LEDGERBAL e âncora | H | fechado | `account_balances`, `opening_balance`, AD-7 "saldo calculado" (barato: `batch_id`, §4) |
| PRD F4 — precondições do fechamento | H | fechado | AD-8 `[ASSUMPTION]` |
| PRD F5 / RUB F-6 — CLAUDE.md, ambiente, Supabase | H | **parcial** | ADR-014/015 gravados; AD-18 backup, migração, aviso de worker, CORS. CLAUDE.md, `.env.example` e a base no Supabase seguem sem dono (§2.8) |
| UX A1 — cobertura B3 por ticker | H | fechado | AD-5 `_ticker_cutoffs` |
| UX C1 — ausente ≠ zero | H | fechado | AD-15 `unavailable_reason` |
| UX C2 — carimbo de data | H | fechado | AD-15 `as_of` = mais antigo, `stale` ≠ defasagem (barato: limites do FR-3 como constantes, §4) |
| UX C3 — cobertura legada | H | fechado | AD-16 passo 2, AD-5 `legacy` |
| UX C5 — recálculo sem conta no front | H | fechado | AD-15 `POST .../preview` |
| RUB F-2 — granularidade do lote | H | fechado | `import_batch_files` |
| RUB F-3 — diagrama × AD-1 | H | fechado | overview na camada 7, casca top-level, `analytics` apagado (ver §3 N6 sobre `auth`) |
| VER F1 — Next com RCE | H | **parcial (baixo)** | Next 16.3.8. React segue 19.2.4 e `eslint-config-next` não foi alinhado (§2.9) |
| VER F2 — shadcn Base UI | H | fechado | AD-17 `-b radix`, `components.json`, proibido `-d` |

## 2. Não fechados por inteiro — texto exato para o spine

### 2.1 Desfazer das derivações (P1, F2, F-1)

O AD-5 diz que o desfazer "remove ... as derivadas (AD-6)". Só que `ingest` (camada 1) não pode
gravar em `asset_operations`, que pertence a `portfolio`. E se `ledger.undo` apagar as transações
primeiro, a FK das operações derivadas falha, ou cada story escolhe o próprio `ON DELETE`.

Durante o `apply`, a derivação também roda duas vezes: `categorize()` chama
`on_transactions_changed` e `ingest` chama `on_batch_applied`.

**Texto (AD-5, bullet do desfazer):**

> Desfazer: na mesma transação, `ingest` chama primeiro os hooks `on_batch_undo(conn, batch_id)`
> registrados, em ordem de camada decrescente, e depois o `undo` de cada adapter. `portfolio`
> remove ali as operações derivadas das transações do lote, antes de `ledger` apagá-las.
> `asset_operations.transaction_id` é FK `ON DELETE RESTRICT`. Dentro do `apply`, a derivação
> roda só por `on_batch_applied`; o `categorize()` chamado pelo adapter não dispara
> `on_transactions_changed`.

### 2.2 Período: definição, início e carimbo (P3 item 5, P5, F-5)

AD-8 diz "trimestre e ano civis". O EXPERIENCE diz "trimestre que o contém; ano até ele; início
até ele". AD-14 aceita `inicio`, que o AD-8 não define. Também não está dito de onde vem o valor
inicial quando o mês anterior está aberto ou não existe.

**Texto (AD-8, substitui "trimestre e ano civis"):**

> Período: `tri` = meses do trimestre civil que contém `periodo`, até `periodo`; `ano` =
> jan..`periodo`; `inicio` = jul/2024..`periodo`. Nunca entra mês posterior a `periodo`. O valor
> inicial vem do mês anterior ao primeiro mês do período: do snapshot, se ele estiver fechado; se
> não, de `build_month_summary(mês anterior, as_of = fim do mês)`. Sem nenhum dos dois, o valor
> sai `Valued` null com `antes_do_primeiro_fechamento`. A resposta traz `source ∈ {snapshot,
> live}` por mês; `as_of` = o mais antigo dos meses; `stale` = OU dos meses.

### 2.3 Mapa de capacidades × AD-8 (P4)

O AD-8 manda toda rota com `periodo`/`leitura` passar por `closing`. O mapa ainda atribui a
`ledger` o FR-15/16/20 (Caixa › Receitas e Gastos, com período), a `portfolio`/`market`/`wallet`
o FR-21/22 (Posições tem Seletor de leitura) e a `planning` o FR-28–31 (aporte do mês).

**Texto (Capability Map, linhas substituídas):**

> | FR-15, FR-16, FR-20 receitas, gastos, poupança | cálculo `ledger/calc`; rota por período `closing` | AD-7, AD-8 |
> | FR-21–FR-27 posições, XIRR, RF, debêntures, corretora, conciliação, preços | fatos e cálculo `portfolio`, `market`, `wallet`; posição/XIRR por período `closing` | AD-6, AD-7, AD-8, AD-11, AD-13 |
> | FR-28–FR-31 aportes | cadastro, distribuição e prévias `planning`; planejado × realizado por período `closing` | AD-8, AD-9, AD-11, AD-12 |

### 2.4 `kind` do grupo e onde "a classificar" conta (P7)

A recópia de `kind` cobre a subcategoria que muda de grupo, mas não o grupo que muda de tipo. Os
grupos e o `kind` das subcategorias de sistema não estão definidos. Uma story põe "Saída a
classificar" em gastos e no consumido; outra a deixa fora.

**Texto (AD-6):**

> O tipo de um grupo com transações não muda. Mudar o tipo = mover as subcategorias, que passa por
> `categorize()` nas linhas afetadas. "Entrada a classificar" e "Saída a classificar" ficam num
> grupo de sistema por tipo (receita/gasto, pelo sinal). Elas entram na receita total e nos gastos;
> nunca em trabalho, resgates, devoluções, dívidas ou custo fixo. O fechamento bloqueia enquanto
> existirem (AD-8).

### 2.5 Casador de custo fixo e dívidas retroativas (P9)

"Menor |Δvalor| e depois |Δdata|" não diz se a ordem é global ou por custo. Ainda falta o
desempate. No retroativo, `ensure_month_plan` soma **todas** as transações em Dívidas. Se uma
delas também é custo fixo casado (ex.: financiamento), o disponível desconta a mesma transação
duas vezes.

**Texto (AD-7, linha do casamento, e AD-8, retroativo):**

> casamento de custo fixo: guloso global. Os pares candidatos (±10%, −5/+5 dias) são ordenados por
> (\|Δvalor\|, \|Δdata\|, `fixed_cost_id`, `transaction_id`), e cada lado casa uma vez. As decisões
> de `fixed_cost_payments` entram antes e retiram os dois lados.
>
> `ensure_month_plan(month, mode='retro')`: dívidas do mês = Σ transações de role `divida` **não
> casadas** a custo fixo.

### 2.6 Fechamento retroativo (P10)

Falta definir o aporte planejado dos meses retroativos, que hoje faz o pendente sair negativo. A
ordem "depois das revisões" não é verificada, e o snapshot não distingue a origem.

**Texto (AD-8, retroativo):**

> `close_retro` aborta se `alembic current` estiver antes da revisão 4 de AD-16. Em
> `mode='retro'`, aporte planejado = null (`nao_definido`) e pendente = null.
> `month_closes.origin ∈ {live, retro}`.

### 2.7 Identidade do ativo (P11)

O passo 4 do AD-12 ("ativos: déficit dentro da classe") exige meta por ativo, mas
`portfolio_targets` não diz se tem `asset_id`. `wallet_positions` (L-BTC × BTC, HYPE em dois
lugares) não liga a `assets`. `month_summary_lines.dimension_id` não tem tipo.

**Texto (AD-11):**

> `portfolio_targets` (`planning`) tem `class` e `asset_id` nullable (NULL = meta da classe).
> `wallet_positions` ganha `asset_id`, resolvido por `asset_aliases(asset_id, chain, symbol)`, que
> pertence a `portfolio`. `month_summary_lines.dimension_id` é `text` com tipo fixo por
> `dimension_kind`: `category` → `categories.id`, `class` → valor do enum, `asset` → `assets.id`,
> `goal` → `goals.id`, `account` → `accounts.id`.

### 2.8 CLAUDE.md, `.env.example` e a base atual (F5, F-6)

O ADR-014 está gravado, mas:

- o CLAUDE.md ainda fixa Supabase, Upstash e Fly/Vercel ("não mudar sem ADR"), além dos gates
  m0–m7;
- o `.env.example` ainda aponta `DATABASE_URL` para um host remoto e `REDIS_URL` para
  `rediss://` (Upstash);
- o spine não diz como a base viva, se ainda está no Supabase, chega ao Postgres do compose, nem o
  que acontece com o projeto Supabase depois.

**Texto (Consistency Conventions › Docs vivos e AD-18):**

> Docs vivos: a 1ª story também reescreve o CLAUDE.md (stack local com o Postgres e o Redis do
> compose; sem Supabase, Upstash, Fly ou Vercel; gates da v2 no lugar de m0–m7; ADR-014/015) e o
> `.env.example` (`DATABASE_URL`/`REDIS_URL` do compose).
>
> AD-18: `DATABASE_URL` e `REDIS_URL` só apontam para `localhost` ou para os serviços do compose.
> A story de ambiente copia a base atual para o Postgres local (`pg_dump` → `pg_restore`, com as
> contagens conferidas) e depois desativa o projeto Supabase e a instância Upstash.

### 2.9 React e eslint-config-next (VER F1)

**Texto (Stack):**

> React | 19.2.9 (mesma minor) · `eslint-config-next` | 16.3.8 (igual ao Next)

## 3. Varredura adversária nova (contradições introduzidas pela revisão)

### N1 — AD-8 "toda rota com `periodo`" captura demais

- **Unidade A:** `GET /api/v1/ledger/transactions?periodo=2026-07`, a lista de fatos da Revisão
  e de Transações. Pela letra do AD-8, essa rota vira de `closing`, e `closing` passa a listar
  transações.
- **Unidade B:** a mesma lista fica em `ledger`, porque é fato e não resumo.
- **Mesmo problema:** os `POST .../preview` de orçamento e distribuição e a edição de dívidas do
  mês têm mês. Uma story os põe em `planning`, outra em `closing`.

**Fix (AD-8):**

> A regra vale para termos de AD-7, resumos e posição/rentabilidade por período. Listas de fatos
> filtradas por mês (transações, operações, lotes) ficam na dona, com `month` ou intervalo de
> datas, nunca `leitura`. Escritas e prévias do mês (`month_plans`, distribuição, dívidas) ficam
> em `planning` e recebem `month`.

### N2 — O snapshot não guarda os termos que a tela do mês fechado mostra

Hoje `month_summary_totals` lista receitas, trabalho, resgates, devoluções, gastos, consumido,
investimento, poupança, planejado/realizado/pendente, patrimônio, aplicado, resultado e saldo
conferido. Faltam disponível, restante, custos fixos, dívidas do mês, financiado por resgate (por
objetivo × por carteira), a caminho, caixa em corretora e taxa de poupança.

Com isso, `closing` só consegue servir Caixa › Orçamento de jul/2026 fechado recalculando ao vivo,
o que fere "nunca recalculado", ou devolvendo nulo.

**Fix (AD-8):**

> `month_summary_totals` guarda todos os termos de AD-7 do mês (inclusive disponível, restante,
> custos fixos, dívidas, financiado, a caminho, caixa em corretora e taxa de poupança). As
> quebras (por categoria, classe, ativo, objetivo, carteira) vão para `month_summary_lines`. Uma
> tela de mês fechado só mostra campos do snapshot; campo novo = coluna nova + refechar.

### N3 — A XIRR de período parte do "patrimônio", que inclui o saldo das contas

- **AD-8:** XIRR do período = **patrimônio** do snapshot anterior + fluxos do período + valor
  final.
- **AD-7:** patrimônio = posições + bloco cripto + caixa em corretora + **saldo das contas**.

Uma story usa o patrimônio inteiro: o saldo bancário entra sem que salário e gastos entrem como
fluxo, e a XIRR fica inflada ou deprimida. Outra story usa só as posições. O resultado diverge do
gate Excel (±0,1 pp).

**Fix (AD-8):**

> XIRR do período: valor investido (posições + bloco cripto + caixa em corretora, **sem** saldo das
> contas) no início, como saída; os fluxos líquidos de investimento datados do período; e o valor
> investido no fim, como entrada. O snapshot grava esse valor investido como total próprio.

### N4 — Idioma dos enums persistidos

- **Consistency Conventions:** "Enums persistidos: `text` + `CHECK`, valores snake inglês".
- **AD-6:** `categories.role` mistura `work_income` com `resgate`, `devolucao`, `divida`,
  `consumo`, `investimento`, `transferencia` e `a_classificar`.
- **AD-11:** a classe é `acoes_br`, `renda_fixa`, `aposentadoria`, `cripto`.
- **AD-10:** a severidade é `divergencia`/`aviso`.

A story da migração segue a convenção e grava `fixed_income`; a story de `planning` segue o AD-11
e lê `renda_fixa`.

**Fix (Consistency Conventions):**

> Enums persistidos: `text` + `CHECK`, snake sem acento; os valores listados em AD-6, AD-10, AD-11
> e AD-15 são os canônicos (exceção à regra do inglês).

A alternativa é traduzir os três ADs.

### N5 — O desfazer apaga `categorization_events`, que o AD-6 declara append-only

- **AD-5:** o desfazer remove "as categorizações ... do lote".
- **AD-6:** `categorization_events` é append-only e sustenta SM-5, SM-6 e SM-C1.

Uma story apaga os eventos, e os SMs perdem histórico. Outra os mantém, e a FK para `transactions`
impede o desfazer. Também não está dito o que acontece com as transações **fora** do lote que
apontam (`category_rule_id`) para uma regra apagada.

**Fix (AD-5/AD-6):**

> O desfazer apaga as `categorization_events` das transações do lote (única exceção ao
> append-only; a FK é `ON DELETE CASCADE`). Transações de fora do lote categorizadas por uma regra
> do lote voltam por `categorize()` sem a regra e ficam `suggestion`/`pending`;
> `category_rule_id` é `ON DELETE SET NULL`.

## 4. Médios/baixos baratos de corrigir no texto

- **N6 — `auth` × `common` na mesma camada.** AD-2 põe `AuthUser` em `common.deps`, o que obriga
  `common` a importar `auth` (hoje `auth/dependencies.get_current_user`). As duas são camada 0, e
  o AD-1 proíbe import na mesma camada. Fix: "`api/auth/` fica entre 0 e 1: importa `common`, e
  `common` nunca importa `auth`; `AuthUser` mora em `auth.deps`."
- **Arredondamento (AD-4).** O AD-4 só arredonda na fronteira HTTP. Subtotais arredondados um a um
  podem não somar ao total arredondado, e o front não pode corrigir. Fix: "cada termo é
  `quantize(0.01, ROUND_HALF_EVEN)` no `calc` antes de somar; o total é a soma dos valores já
  arredondados; o snapshot grava `numeric(14,2)`; razões (`Pct`, XIRR) ficam gravadas como fração
  `numeric` e só viram % no `models.py`. O resultado do `brentq` (float) vira `Decimal` na saída do
  solver."
- **Escopo do `Valued` (AD-15).** "Número exibido = `Valued[T]`" deixa em aberto se o valor de
  cada transação vem embrulhado. Fix: "`Valued` só para valores derivados ou de mercado (termos,
  preço, posição, XIRR); fatos gravados (valor da transação ou da operação) são `Money` puro."
- **Cadastros de mês fechado.** `fixed_cost_payments` e `month_plans` de mês fechado não estão na
  lista de escritas que marcam `dirty`, e não se diz quando o `dirty` zera. Fix: "`month_plans` e
  `fixed_cost_payments` de mês fechado são só leitura (editar exige reabrir); fechar de novo zera o
  `dirty`."
- **`MonthStatusPort` sem métodos.** Fix: "`closed_months(conn) -> set[date]`,
  `mark_dirty(conn, months: set[date]) -> None`".
- **Invalidação no web (AD-17).** `categorize` muda posições (caixinha derivada), mas a regra só
  invalida a própria engine, `closing`, `alerts` e `overview`. Fix: "toda mutação de `ingest`,
  `ledger`, `portfolio` ou `planning` invalida tudo, menos `market` e `jobs`."
- **Aporte de debênture sugerido × AD-9.** A derivação grava o "sugerido", mas a confirmação não
  tem tabela. Fix (AD-9): "`asset_operations.status ∈ {suggested, confirmed}`; confirmar é decisão
  humana; a derivação nunca apaga nem altera `confirmed`."
- **`account_balances.batch_id`.** Sem esse campo, o desfazer não remove o saldo informado do
  lote. Fix: incluir `import_batches ||--o{ account_balances` no ERD e citar no AD-5.
- **Limites do FR-3** (Nubank 7 dias; consolidado no dia 15): Fix: "constantes de `ingest/calc`,
  usadas pelo provider de 'fonte desatualizada'".
- **Papel de subcategoria nova (FR-8).** Fix: "subcategoria criada em Ajustes herda o
  `default_role` do grupo; o papel só muda por Ajustes, com prévia."
