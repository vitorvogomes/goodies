---
review: adversary
target: ../ARCHITECTURE-SPINE.md
lens: "construir duas unidades um nível abaixo que obedecem todo AD à letra e ainda assim montam incompatíveis"
date: '2026-10-17'
verdict: not-ready
---

# Revisão adversária — ARCHITECTURE-SPINE Goodies v2.0

## Veredito

**Não pronto para fatiar em stories.** O spine fecha bem as camadas, o dono de cada tabela e as
fórmulas, mas deixa **três contradições internas** (AD-5 × AD-3/AD-1 na derivação de caixinha; AD-8
× AD-1 nas leituras de período; AD-8 × AD-16 no fechamento em bloco) e **um defeito de semântica**
(AD-8 compara "ao vivo" com congelado para meses passados sem histórico de preços). Com elas, duas
stories pequenas e corretas pela letra produzem números diferentes para o mesmo mês. Encontrei 13
pares: 4 críticos, 7 altos e 2 médios. Todos se fecham com ADs novos ou mais apertados (lista no
fim). Nenhum exige mudar a stack ou o paradigma.

## Método

Para cada par, descrevo duas unidades (story/módulo) que um agente pequeno escreveria só com o
spine, cito os ADs que cada uma cumpre e mostro onde elas quebram. Conferi o código atual quando o
choque depende do esquema existente:

- `api/engines/portfolio/caixinhas.py` deriva operações filtrando
  `transactions.category = ANY('Caixinha/RDB Nubank')` mais tokens ILIKE na descrição;
- `asset_prices` tem PK `ticker` e guarda **só o último** preço (upsert), sem histórico;
- `portfolio_targets` é `UNIQUE (user_id, category)` com `category` = string pt-BR
  ("Ações Nacionais"), sem meta por ativo;
- `asset_operations.asset_symbol` e `asset_category` são texto livre; `wallet_positions` e
  `crypto_cost_basis` usam `asset_symbol` próprio;
- o importer atual grava `kind` na importação via `match_patterns`, e `transactions.kind` tem
  `DEFAULT 'expense'`;
- `hermes/router.py` ainda faz `INSERT INTO transactions` com SQL próprio.

---

## Pares incompatíveis

### P1 — CRÍTICO — Derivação de caixinha/RF/debênture: dois donos e o momento errado

- **Unidade A** (story "adapter Nubank", `ledger`): segue o **AD-5** à letra. As "derivações
  pós-import (operações de caixinha, RF, aporte de debênture sugerido) rodam no `apply` do adapter
  dono, no mesmo lote". O adapter Nubank é de `ledger`, então grava `asset_operations` no próprio
  `apply`.
- **Unidade B** (story "caixinhas como ativo", `portfolio`): segue o **AD-3**, em que só
  `portfolio` escreve `asset_operations`, e o **AD-1**, em que `ledger` (camada 2) não importa
  `portfolio` (camada 3). Ela deriva as operações dentro de `portfolio`, lendo `transactions`, como
  o `caixinhas.py` faz hoje.
- **Choque:**
  1. Duas implementações gravam a mesma operação, ou nenhuma grava. Num lote só de OFX, o adapter
     B3 de `portfolio` nem roda, então B nunca é disparada pelo lote.
  2. A derivação no `apply` roda **antes** da revisão (`categorize()` acontece depois, no fluxo do
     ritual). Se o Vitor corrigir na revisão uma transação de "Caixinha/RDB" para outra categoria,
     ou o inverso, a operação derivada fica errada para sempre. O mesmo acontece no FR-11
     (reaplicar regras) e no desfazer.
  3. A migração do FR-19 (AD-16) move os resgates para o grupo **Resgates** (receita). O filtro por
     categoria de investimento, que B herda do código atual, deixa de ver os resgates, e a caixinha
     só cresce.
- **Fecha com:** um **AD-5 mais apertado**, junto com um AD novo, "Derivação de ativos a partir do
  caixa":
  - Operações derivadas de `transactions` são de `portfolio`. Elas são **derivadas na leitura**
    (AD-9), ou recomputadas por um hook `on_transactions_changed(conn, tx_ids)` que `portfolio`
    registra em `ledger` no startup.
  - `ledger.service` chama esse hook dentro da mesma `conn.transaction()` em `categorize()`, no
    `apply`, no `undo` e na reaplicação.
  - A entrada da derivação é o vínculo explícito transação→ativo (P2), nunca o nome da categoria
    nem o token da descrição.
  - O texto do AD-5 que diz "rodam no `apply` do adapter dono" é removido.

### P2 — CRÍTICO — Qual ativo/objetivo é a origem de um resgate (e o destino de um aporte)

- **Unidade A** (migração FR-19, AD-16): reclassifica os resgates para `Resgates > <destino>`,
  conforme a tabela do party: "Resgates — por destino". O vínculo fica no **nome da subcategoria**.
- **Unidade B** (`portfolio`, AD-11): o vínculo vem do **token da descrição** do OFX ("Caixinha
  SnowTrip"), e `assets.goal_id` liga o ativo ao objetivo.
- **Unidade C** (`planning`, AD-7, "consumo financiado por resgate, por objetivo × por carteira"):
  precisa saber de qual objetivo saiu cada resgate. Ela vai usar A (subcategoria) ou B (token) e
  pode divergir das duas.
- **Choque de dono:**
  - `assets.goal_id` é coluna de tabela de `portfolio` (camada 3) com FK para `goals`, de
    `planning` (camada 4).
  - Pelo AD-11, "o vínculo vem da caixinha nomeada no OFX". Quem cria o objetivo "Snow Trip" ao
    ver uma caixinha nova? Se for `portfolio`, ele escreve `goals` (viola AD-3 e AD-1). Se
    `planning` grava `assets.goal_id`, viola AD-3.
  - Resultado: duas stories legítimas, "objetivos (FR-35)" e "caixinhas", cada uma assume que a
    outra cria o vínculo.
- **Fecha com:** um AD novo, "Vínculo transação→ativo e objetivo→ativo":
  - Existe **um** vínculo, `transactions.asset_id`, nullable, com FK para `assets`. Quem resolve é
    um resolver que `portfolio` registra em `ledger`, chamado só por `categorize()`. Subcategoria e
    descrição passam a ser **entradas** do resolver, não o vínculo.
  - O vínculo objetivo↔ativo fica numa tabela de `planning`, `goal_assets(goal_id, asset_id)`, que
    substitui `assets.goal_id`. `portfolio` recebe por registro a função
    `goal_owned_asset_ids(conn)` para filtrar a base da alocação (AD-1).
  - Objetivo é decisão humana (AD-9): uma caixinha sem objetivo gera o aviso "caixinha sem
    objetivo" com a ação "criar objetivo". Nenhuma engine cria `goals` sozinha.

### P3 — CRÍTICO — "Ao vivo" de um mês passado não é reprodutível, e o aviso de ajuste dispara sempre

- **Unidade A** (`closing`, AD-8): aviso "ajuste em mês fechado" =
  `build_month_summary(ao vivo) − snapshot ≠ 0`, para cada mês fechado.
- **Unidade B** (`market`, ADR-012/AD-15): mantém `asset_prices` com upsert do último preço, que
  já é o esquema atual. A valoração das caixinhas usa o CDI coletado até hoje.
- **Unidade C** (`ledger`, FR-35): editar o valor de um custo fixo altera a linha em
  `fixed_costs`, que não tem vigência.
- **Choque:**
  1. `build_month_summary("2026-07")` ao vivo calcula o patrimônio e o valor por classe/ativo
     (itens congelados pelo FR-32) com o **preço de hoje** e o CDI de hoje. O resultado é
     diferente do congelado. Os ~27 meses fechados disparam o aviso todo dia (fere SM-C2). A prévia
     de reabrir mostra lixo, e reabrir set/2026 em outubro congela de novo com preços de outubro.
  2. Mudar o custo fixo, a meta, a banda ou o objetivo muda o "disponível" ao vivo de todos os meses
     fechados, e o aviso aparece em todos.
  3. O snapshot é gravado arredondado (AD-4, "ao gravar"), enquanto o ao vivo não é. A diferença dá
     ≠ 0 por centavos residuais.
  4. O golden "snapshot = ao vivo no instante do fechamento" (AD-19) passa no teste e falha no dia
     seguinte.
  5. O valor de início de período do FR-22 para um mês aberto depois de outro mês aberto não tem
     snapshot de onde vir.
- **Fecha com:** um **AD-8 mais apertado**:
  - Assinatura `build_month_summary(conn, month, as_of=fim_do_mês)`. Os insumos de mercado entram
    **na data de fim do mês**. Isso exige histórico de preço, `asset_price_history(ticker,
    ref_date)` de `market` (ADR-012 continua para o último preço). Sem preço na data, o valor sai
    `stale` e o ajuste ignora a métrica.
  - Os cadastros que entram no cálculo têm vigência (`fixed_costs.valid_from/valid_to`) ou são
    congelados em `month_plans` ao abrir o mês.
  - O diff do aviso compara só métricas derivadas de **fatos**: fluxos, quantidades e categorias.
    A comparação é feita depois do mesmo arredondamento de saída.
  - Início de período sem snapshot = `build_month_summary` ao vivo do mês anterior, com o mesmo
    `as_of`.

### P4 — CRÍTICO — Leitura de período de mês fechado mora abaixo de `closing`

- **Unidade A** (`planning`, AD-7/AD-15): `GET /api/v1/planning/budget?periodo=2026-07` calcula o
  disponível e o restante **ao vivo**, porque `planning` (camada 4) não pode importar `closing`
  (camada 5) pelo AD-1.
- **Unidade B** (`closing`/`overview`, AD-8): "Mês fechado: toda leitura de período (painel,
  histórico, **orçamento**, **posições por período**) lê o snapshot."
- **Choque:** o mesmo jul/2026 fechado mostra um número na aba Caixa › Orçamento e outro na Visão
  geral e no Histórico. O AD-8 manda o orçamento e as posições por período lerem o snapshot, mas o
  mapa de capacidades põe o FR-17 em `planning` e o FR-21/22 em `portfolio`, que não enxergam
  `closing`. O AD-8 e o AD-1 se contradizem.
- **Fecha com:** um AD novo, "Leituras de período só por `closing`":
  - Todo endpoint que recebe `periodo`/`leitura` é servido por `closing` (ou por `overview`, que
    está acima). Ele devolve as fatias de `MonthSummary` (orçamento, posições, receitas e gastos).
  - `planning` e `portfolio` expõem rotas sem período: cadastros, distribuição do mês corrente e
    posição atual.
  - O mapa de capacidades passa a dizer "FR-17/21/22 leitura por período → `closing`".

### P5 — ALTO — Trimestre com 2 meses fechados e 1 aberto

- **Unidade A** (`overview`, card "tri"): soma os três `MonthSummary` (2 snapshots e 1 ao vivo) e
  tira a **média** das taxas de poupança mensais.
- **Unidade B** (`closing`, FR-34): recalcula a taxa a partir da soma dos numeradores e dos
  denominadores. Usa a XIRR do trimestre a partir dos **fluxos mensais** do snapshot, já que o
  snapshot não guarda fluxos datados.
- **Unidade C** (`portfolio`): faz a XIRR do trimestre com os fluxos diários de
  `asset_operations`.
- **Choque:**
  - O AD-14 diz `leitura ∈ {mes, tri, ano, inicio}`, mas não diz se `periodo=2026-10&leitura=tri`
    é o trimestre-calendário (out–dez, parcial) ou os 3 meses até outubro.
  - Não diz como se agregam razões nem a XIRR.
  - Não diz qual `as_of` e qual `stale` um período misto carrega.
  - Três números diferentes para o mesmo trimestre. A XIRR mensal-agregada também diverge do gate
    Excel (±0,1 pp).
- **Fecha com:** um **AD-14 mais apertado**:
  - `common.dates.resolve_period(periodo, leitura) -> list[month]` é a única resolução. Trimestre =
    trimestre-calendário que contém `periodo`, truncado em `today_brt()`.
  - A agregação é uma função de `closing/calc.py`. Totais aditivos são somados. Razões são
    recalculadas com numeradores e denominadores somados. A XIRR do período usa o patrimônio de
    início (snapshot ou ao vivo, P3), os fluxos **datados** (o snapshot passa a guardar os fluxos
    diários por classe em `month_summary_lines`, `dimension_kind = 'flow_day'`) e o patrimônio de
    fim.
  - A resposta traz, por mês, `source ∈ {snapshot, live}`. `as_of` = o mais antigo dos meses.

### P6 — ALTO — Status do mês é necessário abaixo da camada 5 e não há porta definida

- **Unidade A** (`ingest`, FR-6/FR-33): a prévia do desfazer e do lote precisa dizer "este lote toca
  set/2026, que está fechado". Para isso, `ingest` (camada 1) consulta `month_closes`.
- **Unidade B** (`ledger`, FR-11, prévia de reaplicar; providers de "saldo divergente" e "custo
  fixo atrasado"): precisa do status do mês. Cada story inventa um registro diferente no
  `main.py`, ou lê `month_closes` por SQL, o que viola o AD-3, já que a dona está acima.
- **Unidade C** (AD-10): `alert_provider(conn, ctx)`. Cada engine define o próprio `ctx`.
- **Choque:** o AD-1 permite "registro no startup", mas sem uma porta nomeada saem N callbacks
  incompatíveis e `ctx` com formatos diferentes. Os providers baixos também não sabem se uma
  divergência é de mês fechado (o que vira só "ajuste em mês fechado") ou aberto.
- **Fecha com:** um **AD-1/AD-10 mais apertado**:
  - `common.periods.MonthStatusPort` com `closed_months(conn) -> set[date]`, implementado por
    `closing` e registrado no startup. É a única forma de uma engine abaixo de 5 saber o status.
  - `common.alerts.AlertContext` congelado, com `owner_id`, `today`, `closed_months` e `periodo`,
    é o único `ctx`.

### P7 — ALTO — `transactions.kind` na importação, antes da categorização, e o tipo do grupo mutável

- **Unidade A** (adapter Nubank, AD-5/AD-6): "kind é gravado **só** por `categorize()`". O adapter
  insere as linhas e chama `categorize()` só nas que têm regra. As linhas "sem sugestão" ficam com
  `category_id NULL` e `kind` no default do banco, `'expense'`.
- **Unidade B** (`ledger/calc` consumido): lê o tipo pelo `JOIN category_groups`, e as linhas NULL
  somem.
- **Unidade C** (`closing`, resumo): lê `transactions.kind`, e a mesma linha vira gasto.
- **Unidade D** (FR-8 em Ajustes): mover uma subcategoria para um grupo de outro tipo, ou mudar o
  tipo de um grupo, deixa as cópias em `transactions.kind` velhas.
- **Choque:** o AD-6 marca como `[ASSUMPTION]` "pendente conta com a categoria proposta", mas não
  diz o que conta uma linha **sem** proposta. A saída é consumido ≠ entre o painel e o
  fechamento. O Hermes (hoje com `INSERT` próprio) passa a usar `ledger.service`, mas qual função
  e com qual categoria?
- **Fecha com:** um **AD-6 mais apertado**:
  - Toda inserção passa por `ledger.service.insert_transactions()`, que chama `categorize()` na
    mesma transação.
  - `category_id` é NOT NULL. Sem proposta, recebe a subcategoria de sistema "A classificar"
    (gasto, se o valor é negativo; receita, se é positivo).
  - As leituras usam **só** a cópia `transactions.kind`, nunca o JOIN.
  - Mudar o tipo de um grupo ou mover uma subcategoria chama `categorize()` em todas as linhas
    afetadas, na mesma transação. Se houver mês fechado, o efeito segue o FR-33.

### P8 — ALTO — Papéis semânticos em categorias editáveis

- **Unidade A** (`ledger/calc`, AD-7): "transações em Dívidas" e "receita do trabalho por grupo de
  categoria" são identificadas pelo **nome**.
- **Unidade B** (migração AD-16): semeia grupos com uuid fixo e usa o uuid.
- **Unidade C** (FR-8): o Vitor renomeia "Trabalho" para "Salário", ou cria o grupo de receita
  "Aluguel". A unidade A quebra, e não se sabe se "Aluguel" é receita do trabalho.
- **Choque extra:** o glossário diz "receita do trabalho = receita **sem os resgates**". Com isso,
  **Devoluções** (grupo de receita) entra na receita do trabalho, e o consumido também desconta as
  devoluções. Uma story conta a devolução duas vezes a favor da poupança e outra a ignora. O gate
  de jun/2026 passa nos dois casos (não houve repasse), então a divergência é silenciosa.
- **Fecha com:** um AD novo, "Papéis de grupo":
  - `category_groups.role text CHECK (role IN ('work','resgate','refund','expense','debt',
    'card_bill','investment','transfer'))`. É atribuído pelo sistema e não pode ser editado pela
    UI. `debt` e `card_bill` podem ser papéis de subcategoria, em `categories.role`.
  - A tabela do AD-7 passa a definir cada termo por papel, não por nome.
  - Fica explícito: receita do trabalho = `role = 'work'`, e as devoluções só abatem o consumido.

### P9 — ALTO — Custo fixo casado que também está em Dívidas, e casamento um-para-muitos

- **Unidade A** (`ledger/calc.consumed`): consumido = gastos − **valor da transação** dos custos
  fixos casados − devoluções − transações em Dívidas.
- **Unidade B** (`planning/calc.available_for_spending`): disponível = trabalho + resgates −
  **valor cadastrado** dos custos fixos − aporte − dívidas do mês.
- **Choque:**
  1. Um "Financiamento" cadastrado como custo fixo e categorizado em Dívidas é subtraído **duas
     vezes** do consumido. Ele também entra no disponível pelo custo fixo e outra vez pelas dívidas
     do mês.
  2. O casamento ±10% / ±5 dias é derivado na leitura (AD-9) sem regra de exclusividade. Dois
     custos com valores parecidos (internet e celular) casam a mesma transação.
  3. A e B usam montantes diferentes (transação × cadastro), e o restante não fecha com o mock
     (R$ 6.912,37 / R$ 8.405,59).
- **Fecha com:** um **AD-7/AD-9 mais apertado**:
  - `ledger/calc.match_fixed_costs()` é o único casador. O casamento é **um-para-um**: guloso por
    |Δvalor| e depois |Δdias|, com desempate por id. A decisão manual em `fixed_cost_payments`
    vence.
  - Cada transação cai em **um** balde de dedução, com a precedência custo fixo > dívida >
    devolução.
  - Custo fixo do mês = valor da transação casada, se pago, ou o valor cadastrado, se pendente. O
    mesmo número serve aos dois termos.

### P10 — ALTO — Fechamento retroativo e em bloco: quem grava `month_plans` e por qual caminho

- **Unidade A** (migração FR-7, jul/2024–mai/2026 "fechados em bloco **na migração**"): o AD-16
  manda que a migração seja SQL idempotente em Alembic, então a story grava `month_closes`,
  `month_summary_*` e as dívidas do mês **em SQL**. Isso é uma segunda implementação do resumo, o
  que viola o AD-8.
- **Unidade B** (`closing`, AD-8, "mesmo caminho"): usa `build_month_summary` em Python, chamado
  de `api/scripts/oneoff`. O AD-16 proíbe o oneoff para o modelo.
- **Dono:**
  - Pelo party, "dívidas do mês nos retroativos = soma das transações em Dívidas", mas
    `month_plans` é de `planning` e `closing` só grava as próprias tabelas (AD-3). Ou `closing`
    viola o AD-3, ou `planning` precisa saber que o mês é "retroativo", o que viola o AD-1 sem a
    porta do P6.
  - O aporte planejado retroativo não existe, então o pendente fica negativo ou sem sentido.
- **Ordem:** se o fechamento em bloco rodar antes da revisão que move as 18 faturas de Dívidas
  para Cartão de crédito, o pré-preenchimento de dívidas inclui ~R$ 9,5 mil.
- **Agravante:** o custo fixo cadastrado hoje aplicado a 2024 dá um disponível falso (ver P3).
- **Fecha com:** um AD novo, "Fechamento retroativo":
  - É um comando `closing.service.close_retro(conn, months)` exposto por CLI (`python -m
    api.commands.close_retro`). Ele verifica que o Alembic está em head ≥ a revisão das
    reclassificações e chama `build_month_summary`.
  - Antes, ele chama `planning.service.ensure_month_plan(month, mode='retro')`. O dono continua
    sendo `planning`, que calcula o padrão a partir do papel `debt` (P8). O planejado = realizado,
    marcado "não planejado".
  - O snapshot grava `origin ∈ {live, retro}`. O texto do FR-7 "na migração" vira "logo após a
    migração, pelo comando".

### P11 — ALTO — Identidade do ativo: chave do backfill × strings legadas

- **Unidade A** (migração `assets`, AD-11/AD-16): cria `assets(id uuid, key, class)` com `class` em
  snake inglês (Consistency Conventions: "valores snake inglês") e adiciona
  `asset_operations.asset_id`.
- **Unidade B** (`market`, ADR-012): o worker continua fazendo upsert em `asset_prices` por `ticker`
  (global, sem `user_id`), e as chaves Redis continuam `price:b3:PETR4`.
- **Unidade C** (`portfolio` valoração e metas): junta `assets.key = asset_prices.ticker`.
  `portfolio_targets` continua `UNIQUE(user_id, category)` com "Ações Nacionais" (pt-BR, string do
  `AssetCategory`), e não há meta por ativo, embora o AD-11 e o Structural Seed digam "classe→ativo".
- **Unidade D** (`closing`): grava `month_summary_lines.dimension_id` = `asset_symbol` texto para
  ativo e "Renda Fixa" para classe.
- **Unidade E** (`wallet`): o mesmo HYPE vem de dois lugares, e L-BTC × BTC são símbolos
  diferentes. As linhas de `wallet_positions` não têm `assets`, mas o AD-12, passo 4, distribui
  "cripto pelo valor atual" **por ativo**.
- **Choque:**
  - A classe em snake não casa com os textos pt-BR legados.
  - Renomear um ativo em Ajustes (FR-35) órfã as linhas de histórico.
  - O "ativo cripto" tem dois donos implícitos (`wallet` por símbolo, `portfolio` por `assets`).
  - `dimension_id` muda de tipo conforme a story.
- **Fecha com:** um **AD-11 mais apertado**:
  - `assets.id` é a **única** referência cruzada a ativo: `asset_operations`, `portfolio_targets`
    (que ganha `asset_id` nullable, `NULL` = meta de classe), `debentures`, `goal_assets` e
    `month_summary_lines`.
  - `assets.key` é imutável e igual ao `asset_symbol` legado, único por usuário. `assets.price_ref`
    é o ticker de mercado. `market` continua indexado por ticker e recebe de `portfolio` a lista de
    `price_ref` (registro no startup).
  - A classe é um enum em `common` (snake), com rótulo pt-BR só na UI. A migração mapeia os textos
    legados.
  - Os ativos cripto são linhas de `assets` (`class = crypto`), com `asset_aliases(asset_id, chain,
    symbol)` para os símbolos de `wallet`.
  - `dimension_id` tem tipo fixo por `dimension_kind`: category → `categories.id`, class → valor do
    enum, asset → `assets.id`, goal → `goals.id`.

### P12 — MÉDIO — Desfazer o lote × decisões que apontam para linhas do lote

- **Unidade A** (`ingest`, AD-5): o desfazer remove por `batch_id` as linhas, as categorizações e as
  regras `created_in_batch`.
- **Unidade B** (`ledger`, FR-18): o Vitor confirmou um custo fixo pago com uma transação desse
  lote, e `fixed_cost_payments.transaction_id` é uma FK.
- **Unidade C** (`ledger`, FR-11): o Vitor reaplicou uma regra criada no lote a transações
  **antigas**, que ficam com `category_source = rule` apontando para uma regra apagada.
- **Choque:** ou o desfazer falha por FK (e o Vitor não consegue desfazer), ou cada story escolhe o
  próprio `ON DELETE` e sobram decisões órfãs. As transações antigas ficam com uma categoria de
  regra que não existe.
- **Fecha com:** um **AD-5 mais apertado**:
  - Cada dona registra `on_batch_undo(conn, batch_id)` em `ingest`.
  - As tabelas de decisão que apontam para `transactions` declaram `ON DELETE CASCADE`, e isso fica
    no Seed.
  - As transações fora do lote categorizadas por uma regra do lote voltam a `categorize()` sem essa
    regra.
  - A prévia do desfazer lista os meses fechados afetados, via a porta do P6.

### P13 — MÉDIO — Invalidação do frontend

- **Unidade A** (`web/lib/ledger.ts`, AD-17): a mutação `categorize` invalida `['ledger']`,
  `['closing']` e `['overview']`.
- **Unidade B** (`web/lib/planning.ts`): `['planning','budget',periodo]`. Também
  `['portfolio','positions']` (caixinha derivada, a caminho) e `['alerts']` (contador de "a
  revisar"). Todas ficam velhas depois de A. O import (`ingest`) afeta tudo.
- **Choque:** a regra "prefixo da engine + closing + overview" não cobre as dependências reais entre
  engines. O formato da chave de período também não está fixado: `{periodo, leitura}` como objeto,
  ou posicional.
- **Fecha com:** um **AD-17 mais apertado**:
  - É um app de usuário único e o volume é pequeno, então toda mutação chama
    `queryClient.invalidateQueries()` (tudo). Alternativa: um mapa estático de dependências em
    `web/lib/query-keys.ts`.
  - A chave tem a forma `[engine, recurso, {periodo, leitura}]`, construída por um helper único.

---

## Outros furos menores (sem par completo)

- **Cobertura "por fonte e conta":** `import_batches` cobre "conta/corretora", mas a corretora é o
  texto `asset_operations.broker`, enquanto a conta é `accounts.id` (que tem `type 'broker'`). É
  preciso fixar que a corretora também é uma linha em `accounts`, e que `import_batches.account_id`
  é sempre FK.
- **Percentual:** pelo AD-4, os percentuais saem "já em %". O `xirr()` atual devolve uma fração. É
  preciso definir em que unidade `month_summary_lines.value` grava percentuais: fração, com a
  conversão só em `models.py`.
- **Desempenho dos avisos:** o provider de "ajuste em mês fechado" roda `build_month_summary` ao
  vivo para ~27 meses a cada leitura da central. Isso pode estourar os 3 s. Com P3 resolvido, o diff
  usa só os fatos. Ainda assim, vale uma regra: comparar um hash dos fatos do mês, guardado no
  snapshot.
- **Hermes:** o AD-3 diz "hermes grava via `ledger.service`", mas não nomeia a função. Com P7, é
  `insert_transactions()`.

## ADs a adicionar ou apertar (resumo)

| # | AD | Ação | Fecha |
| --- | --- | --- | --- |
| 1 | AD-5 + novo "Derivação de ativos a partir do caixa" | derivação em `portfolio` por hook `on_transactions_changed` ou na leitura; tirar do `apply` do adapter `ledger` | P1 |
| 2 | Novo "Vínculos transação→ativo e objetivo→ativo" | `transactions.asset_id` por resolver de `portfolio`; `goal_assets` em `planning` no lugar de `assets.goal_id`; objetivo é decisão humana | P2 |
| 3 | AD-8 | `build_month_summary(month, as_of)`; histórico de preço; cadastros com vigência; diff só de fatos, depois do arredondamento | P3, P10 |
| 4 | Novo "Leituras de período só por `closing`" + AD-14 | endpoints com `periodo` em `closing`/`overview`; `resolve_period`; agregação de mês misto; fluxos datados no snapshot | P4, P5 |
| 5 | AD-1 / AD-10 | `MonthStatusPort` e `AlertContext` em `common` | P6, P10, P12 |
| 6 | AD-6 + novo "Papéis de grupo" | inserção sempre com `categorize`; "A classificar"; recópia ao mudar tipo; `role` de grupo/subcategoria; devoluções fora da receita do trabalho | P7, P8 |
| 7 | AD-7 / AD-9 | casamento de custo fixo um-para-um, balde único de dedução, mesmo montante nos dois termos | P9 |
| 8 | Novo "Fechamento retroativo" | comando `close_retro` após as revisões; `planning.ensure_month_plan(mode='retro')`; `origin` no snapshot | P10 |
| 9 | AD-11 | `assets.id` como única referência; `key` imutável, `price_ref`; classe enum snake; cripto em `assets` com aliases; `dimension_id` tipado | P11 |
| 10 | AD-5 (desfazer) | `on_batch_undo` por dona; `ON DELETE` declarado; recategorizar fora do lote | P12 |
| 11 | AD-17 | invalidar tudo (ou mapa estático); helper de chave | P13 |
