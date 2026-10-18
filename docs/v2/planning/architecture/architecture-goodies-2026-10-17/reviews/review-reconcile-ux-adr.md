---
title: "Review — reconciliação do spine com UX, party mode, ADRs e CLAUDE.md"
target: ../ARCHITECTURE-SPINE.md
date: 2026-10-17
inputs:
  - ../../../ux-designs/ux-goodies-2026-10-17/DESIGN.md
  - ../../../ux-designs/ux-goodies-2026-10-17/EXPERIENCE.md
  - ../../../../party-mode/2026-10-17-abertura-arquitetura.md
  - .claude/memory/decisions.md (ADR-001..013; ADR-011 revertido por design)
  - CLAUDE.md, .claude/memory/conventions.md, .claude/memory/security.md
  - código atual (api/engines/*, api/db/migrations) para checar fatos
verdict: needs-revision
---

# Reconciliação: spine × UX × party mode × ADRs

**Veredito.** A estrutura do spine está correta e quase todo o núcleo do party mode foi
incorporado: `build_month_summary` único, versões, consumido e financiado, AD-12 e AD-13. Faltam
quatro coisas antes de travar:

1. Um contrato para "ausente ou indisponível" e para proveniência, que a UX exige em toda tela.
2. Duas peças de dados sem as quais FR-3, FR-7 e FR-26 não fecham: a cobertura dos dados legados
   e as quantidades do consolidado B3.
3. Uma regra de dedup da B3 que hoje sustenta a correção e que o AD-5 apaga sem dizer.
4. Vários ADRs e regras do CLAUDE.md que o spine enfraquece ao omiti-los ou ao mudar o dono, sem
   registrar a mudança.

Severidade: **H** bloqueia a correção ou contradiz uma decisão; **M** é uma lacuna que vai gerar
implementações divergentes; **L** é higiene.

---

## A. Contradições e ADRs enfraquecidos

| # | Sev | Achado | Fonte | Correção sugerida |
|---|---|---|---|---|
| A1 | H | **A regra de cobertura B3 foi apagada.** O AD-5 diz "dedup segue o `external_id`… `operation_hash` da B3". O código atual (`portfolio/b3_import_service.py`, docstring "load-bearing") afirma o contrário: o `operation_hash` **não** deduplica movimentação × negociação, porque a liquidação em D+2 muda a data. O import aceita só a cauda mais nova, por ticker, do que outra proveniência ainda não cobriu, e informa o que pulou (`skipped_overlap`). Seguir o AD-5 ao pé da letra duplica operações e quebra o XIRR. | código m4; memória `m4-ingestao-atualizacao` | No AD-5, separar **dedup na fonte** (FITID, `operation_hash`) de **cobertura entre fontes** (corte por ticker no `plan` do adapter B3, com contagem de pulados na prévia). |
| A2 | M | **O dono de `asset_prices` mudou sem registro (ADR-012).** O ADR-012 define `portfolio.service.upsert_price` como o único ponto de escrita de preço: precedência `is_manual`, invalidação do cache de preço e do de XIRR. O Structural Seed passa `asset_prices` para `market` e não diz nada sobre o chokepoint, a precedência ou a invalidação. | ADR-012, ADR-004, ADR-008 | Declarar no AD-3/AD-11: `market.service.upsert_price` vira o chokepoint; `is_manual` sempre vence e nunca fica stale; o worker nunca sobrescreve; o XIRR é invalidado por um helper de `common.cache` (AD-1). Registrar como emenda ao ADR-012. |
| A3 | M | **ADR-005 (Liquid dedicado) ausente, com risco de unificação.** O spine põe o scan em `wallet`. O CLAUDE.md fixa o caminho `api/engines/market/fetchers/wallets/liquid.py`, onde os fetchers estão hoje. A migração para o layout do AD-2 é o momento clássico de alguém criar um "cliente Blockstream" comum ao BTC e ao Liquid, que têm a mesma API Esplora. | ADR-005, ADR-013, CLAUDE.md | Dizer onde os fetchers de carteira moram (`wallet/fetchers/` ou continuam em `market`), atualizar o caminho no CLAUDE.md e incluir a invariante: "Liquid é um cliente dedicado e multi-asset (L-BTC + L-USDT); proibido reaproveitar código do fetcher BTC; SideSwap entra manual". |
| A4 | M | **ADR-002 e ADR-008 (XIRR) só aparecem de passagem.** O AD-7 não lista "rentabilidade" nem "resultado dos investimentos". O AD-2 só admite `calc.py`, mas o CLAUDE.md fixa `portfolio/xirr.py`. A proibição de `(resultado−aplicado)/aplicado` não aparece em lugar nenhum, e a UX mostra "aplicado" e "resultado" lado a lado. O cache de XIRR de 1 h, invalidado a cada nova operação, não cobre o `apply` nem o `undo` do lote (AD-5), e a chave atual (`xirr:consolidated:{user}`) ignora o `periodo`/`leitura`. | ADR-002, ADR-008, CLAUDE.md | Incluir no AD-7 as linhas *rentabilidade* (XIRR via `brentq` em `portfolio/xirr.py`, núcleo puro; nominal e real por IPCA; % a.m. por ativo, exceto RF e cripto; nunca por ativo cripto) e *resultado dos investimentos* (absoluto, sem %). No AD-5: `apply`/`undo` que tocam `asset_operations` invalidam `xirr:*`. Chave com período. |
| A5 | M | **ADR-006 (auth) é citado, mas não aparece em nenhuma regra.** Com páginas client (AD-17) e TanStack Query, o comportamento diante de um 401 fica sem definição: renovar pelo cookie, repetir a chamada, ou cair no login e voltar à mesma rota e período (EXPERIENCE › Sessão expirada). Falta também afirmar o access token só em memória, o refresh em cookie httpOnly e o token de serviço do Hermes. | ADR-006, CLAUDE.md, EXPERIENCE | Incluir um bullet no AD-15/AD-17: "auth inalterada (ADR-006); o wrapper de fetch em `web/lib` faz refresh no 401 e redireciona para `/login?next=<rota+query>`; nada em localStorage". |
| A6 | M | **Supersessões sem ADR.** (a) O AD-18 suspende o deploy Fly/Vercel e o Upstash do ADR-001 e do CLAUDE.md. (b) O FR-19 (resgate vira receita) **reverte o ADR-011**, mas o spine nunca cita o ADR-011. O `decisions.md` exige um ADR novo para qualquer mudança. Há ainda cláusulas do ADR-011 que continuam valendo e não foram ditas: não rodar `reset_ledger.py`; caixinhas são ativos RF; Santander é receita externa. | decisions.md cabeçalho, ADR-001, ADR-011 | Criar ADR-014 (v2.0 local, deploy na v2.1) e ADR-015 (resgates como receita, supersede o ADR-011, listando as cláusulas que permanecem). Referenciar os dois no AD-16/AD-18. |
| A7 | M | **Consequências da reversão do ADR-011 não estão modeladas.** Com resgates `kind=receita`, o "realizado" deixa de ser líquido de resgates. A derivação das operações de caixinha (AD-5) passa a ler os resgates do grupo Resgates. O "aportado" do objetivo (AD-11 diz "aportes líquidos") precisa de definição explícita. E o gate m2 (XIRR B3+TD = 10,85%) precisa continuar valendo. | ADR-011, memória `caixinha-resgate-includes-interest` | No AD-7, definir o realizado como bruto (saídas para investimento) e o aportado do objetivo como aportes − resgates do ativo. No AD-16, acrescentar o invariante "XIRR consolidado inalterado pela reclassificação". |
| A8 | M | **Convenção de log mais fraca que a regra de segurança.** O spine diz "nunca valores de segredo". O `security.md` §6 e o CLAUDE.md dizem também **nunca valores financeiros em texto plano**. | security.md | Na linha "Logs": "nunca segredos nem valores financeiros (logar ids e contagens)". |
| A9 | M | **AD-17 contradiz `conventions.md`.** O spine diz "páginas são client components"; o `conventions.md` diz "Server Components por padrão; dados iniciais via RSC". A lista de atualizações do `conventions.md` na Consistency Conventions não inclui esse ponto, nem a troca de tokens `text-gain`/`text-loss` → `positive`/`negative`, nem JetBrains → Geist Mono. | conventions.md, DESIGN › Colors | Acrescentar esses três itens à lista de atualização do `conventions.md`. |
| A10 | L | O ADR-004 fixa `{"value": null, "stale": true, "last_updated": null}`; o AD-15 usa `as_of`. Dois nomes para o mesmo campo. | ADR-004 | Escolher um nome (sugestão: `as_of`) e registrar como emenda ao ADR-004. Ver C1. |
| A11 | L | Os enums de severidade (`divergencia`/`aviso`) e as chaves de aviso (`saldo_divergente`) estão em português, contra a convenção "enums em snake inglês" do próprio spine. | spine › Consistency | Usar `divergence`/`warning` (o rótulo pt-BR fica no front) ou declarar a exceção. |

## B. Decisões do party mode que não chegaram ao spine

| # | Sev | Decisão aprovada | Estado no spine | Correção |
|---|---|---|---|---|
| B1 | M | §4: nos meses fechados retroativamente, **Dívidas do mês já vem preenchido** com a soma das transações em Dívidas daquele mês. | Ausente. O AD-8 (retroativo) e o `month_plans` não dizem nada. | Uma linha no AD-8 › Fechamento retroativo. |
| B2 | M | §3: preencher `category_source` com **"regra" se um padrão atual casa com a descrição; senão "manual"**. É isso que protege a curadoria (FR-11). | O AD-16 cita só "`category_source`", sem a regra. | Escrever a regra no AD-16 e acrescentar o invariante "nenhuma transação curada vira `rule`". |
| B3 | M | §3: as reclassificações rodam **antes dos fechamentos retroativos**. | Não há ordem entre as revisões de dado (AD-16) e o fechamento retroativo (AD-8). | No AD-16, as revisões de categoria e de resgate precedem qualquer `month_closes`; o fechamento retroativo checa a revisão mínima. |
| B4 | M | §6: o gráfico se chama **"Receitas × consumido"** (receita do trabalho, consumido, média 12m). A UX desenha "Gastos por categoria" (por grupo × anterior × média). **Os insumos divergem.** | O spine não resolve o conflito. O AD-8 não lista quais totais o snapshot guarda. | Decidir entre os dois (ou manter ambos). No AD-8, enumerar os totais tipados: receita do trabalho, resgates, gastos, consumido, aporte planejado, realizado, a caminho, **aplicado** (série do gráfico de patrimônio), patrimônio, resultado, poupança. A média 12m é derivada. |
| B5 | L | §2: **Caixinha Turbo e Caixinha Extra** são RF de longo prazo (`goal_id NULL`). | Ausente. O backfill de `assets` (AD-11/AD-16) pode vinculá-las a objetivos pelo nome. | Uma linha no backfill de `assets`. |
| B6 | L | §1: cripto marcada "estimada" no fechamento retroativo. Está **aprovado**. | O AD-8 marca como `[ASSUMPTION]` junto com o "aplicado do bloco", que é novo. | Separar o que foi aprovado ("estimada") do que é suposição nova (aplicado do bloco, "patrimônio não coberto"). |
| B7 | L | §3: a coluna-texto `category` fica por uma versão; `fixed_costs.category_id`; regras com origem "legado". | O ERD não liga `categories` a `fixed_costs`. `category_rules` não tem coluna de origem. | Acrescentar `fixed_costs.category_id` e `category_rules.origin ∈ {legacy, review, manual}`. |

Já incorporados (ok): função única e versões (AD-8); diff ao vivo − congelado; cobertura por
fonte no fechamento; objetivo dono de ativos e base `goal_id IS NULL` (AD-11); rateio e reserva
de 12 meses (AD-12); consumido, dívidas e financiado em duas linhas (AD-7); tabela de tolerâncias
(AD-13); itens adiados (Deferred).

## C. Decisões de UX que dependem de backend/API

| # | Sev | Necessidade da UX | Lacuna | Correção |
|---|---|---|---|---|
| C1 | H | **Ausente ≠ zero, com motivo.** Casos: "Sem aporte planejado" (R$ 0,00 + "não definido"), "Dívidas vazio" ("sem dívidas informadas"), "aguardando IPCA", "Disponível a partir do primeiro mês fechado", "sem preço" ("—"), "Sem metas", "Consolidado B3 não importado". | O spine não tem convenção. O front não pode inferir, e o AD-4 o proíbe de calcular. O `month_plans` precisa aceitar nulo. | No AD-15, um campo indisponível sai como `null` + `unavailable_reason` (enum: `not_set`, `awaiting_ipca`, `before_first_close`, `no_price`, `no_targets`, `no_source`). Os campos manuais aceitam nulo no banco. |
| C2 | H | **Carimbo de data (Data stamp).** Data por número, fonte e hora no tooltip; com várias fontes, vale a **mais antiga**; ponto de aviso conforme os limites do FR-3. | O AD-15 só diz "`as_of` junto". Não define o formato, a regra do mínimo nem quem decide a defasagem. O spine também mistura dois "stale": falha de API externa (ADR-012) e defasagem de arquivo (FR-3: Nubank 7 dias; consolidado no dia 15). | Formato `{value, as_of, source, stale}`. `as_of` derivado = mín. das fontes, calculado no back. Os limites do FR-3 moram num só lugar (`ingest`, junto com a cobertura), e o provider do aviso "fonte desatualizada" os usa. |
| C3 | H | **Cobertura dos dados legados.** "Atualizado até", lacunas, o Assistente de recuperação ("a base vai até 31/05/2026") e "jul/2024–mai/2026 fechados em bloco". | O AD-5 diz que a cobertura vem **só** de `import_batches`. Como nada de jul/2024 a mai/2026 tem lote, os avisos de lacuna disparam para dois anos e o assistente não acha onde a base termina. | O AD-16 cria um lote `legacy` por fonte e conta (período = mín./máx. das linhas) e preenche `batch_id` e `source` das linhas antigas. O lote legado não pode ser desfeito. |
| C4 | H | **Conciliação por quantidade contra o consolidado B3** (AD-13, FR-26) e **patrimônio retroativo do consolidado** (AD-8). | Hoje o consolidado **só aplica preços** (`b3_import_service`): nenhuma tabela guarda as quantidades do extrato. O Structural Seed também não tem essa tabela. | Criar uma tabela de posições do consolidado, dona `portfolio`, por (mês, ativo, qtd, valor, `batch_id`), gravada no `apply` do adapter consolidado. |
| C5 | H | **Recalcular "na hora" sem conta no front.** Travar um valor e redistribuir; "Disponível depois do aporte" enquanto digita; Dívidas inline → "a conta recalcula"; subtotais por mês na Revisão. | O AD-4 proíbe aritmética de dinheiro no front e o AD-9 só grava travas. Não há padrão de **cálculo sem gravar**. | Endpoints de simulação (`POST …/distribution:preview`, `…/budget:preview`) que chamam o mesmo `calc` e não gravam; o hook TanStack faz debounce. Os subtotais da Revisão vêm da API. |
| C6 | M | **Prévias de mutação com o efeito em números.** Desfazer ("Remove 43 transações, 2 operações, 38 categorizações e 2 regras"; "lote em mês fechado vira ajuste"); Reaplicar regras (antes × depois, "{n} manuais intactas", "{n} em meses fechados"); Proposta de regra ("Afeta {n} outras"); Reabrir (congelado × recalculado). | Só o import tem `plan`. O `SourceAdapter.undo` não tem prévia. As regras não têm dry-run. | Uma convenção no AD-5/AD-15: toda mutação em lote tem `plan_*` (ou `?dry_run=true`) que devolve as contagens e os meses fechados afetados, com a mesma função do `apply`. |
| C7 | M | **Seletor de período** lista os meses com o selo "aberto", "fechado" ou "ajuste"; o Sino conta todos os avisos ativos em toda tela; o Painel carrega em < 3 s. | Detectar "ajuste" = `build_month_summary(ao vivo) − snapshot` **para cada mês fechado** (cerca de 28, de jul/2024 em diante), a cada contagem do Sino e a cada abertura do seletor. Nenhum endpoint de status de meses foi definido. | Endpoint `closing/months` com status. Detecção barata: só há candidato a ajuste se uma linha do mês mudou depois de `closed_at` (sinal derivado de `updated_at`/lote); o diff completo só roda na prévia de reabrir. |
| C8 | M | **Central de avisos:** "a ação leva à tela já filtrada"; ordem divergências → avisos, mais recentes primeiro; "Dispensar" só em alguns tipos. | O `Alert` tem `key`, `fingerprint` e severidade. Faltam o alvo da ação (rota + query), uma data para ordenar (os avisos são compute-on-read e não têm "criado em") e o indicador de "dispensável". Os tipos "ajuste em mês fechado" e "mês aberto há mais de 10 dias" não têm provider dono. | Fixar o formato: `Alert{key, fingerprint, severity, type, message_params, action{label, href}, occurred_on, dismissible}`. O provider de `closing` emite os dois tipos de mês. |
| C9 | M | **Linha expandida de Transações:** "fonte, lote e **regra aplicada**". | O AD-6 guarda `category_source`, mas não **qual** regra. Desfazer um lote apaga regras `created_in_batch` que podem ter categorizado transações de outros lotes. | Acrescentar `transactions.category_rule_id` (FK com `ON DELETE SET NULL`). No AD-5, definir o que acontece com as transações categorizadas por uma regra desfeita (sugestão: viram `suggestion` pendente). |
| C10 | M | **Reserva de emergência:** alvo = multiplicador × custos fixos (6× por padrão), editável em Ajustes. | O AD-12 usa "falta" e o horizonte de 12 meses, mas não diz de onde vem o alvo da reserva nem onde mora o multiplicador. | No AD-11/AD-12: o alvo da reserva é derivado (multiplicador × soma dos custos fixos cadastrados), e `goals` guarda o multiplicador e o horizonte. |
| C11 | M | **Selo "manual"** em três sentidos: categoria (AD-6, ok); preço manual (ADR-012 `is_manual`); posição manual de carteira (ADR-013: SideSwap/Liquid, editável inline). Mais "Marcar pago manualmente" (AD-9, ok). | A API não promete expor `is_manual` em preços e posições. A UX não tem tela para a posição manual de carteira (o ADR-013 exige edição inline). O FR-27 recusa preço manual em ativo com fonte, mas a regra não tem dono. | O modelo de posição/preço expõe `origin ∈ {market, manual, calculated}`. A validação do FR-27 fica no chokepoint (A2). Abrir um ponto de UX: posição manual no bloco cripto ou em Ajustes. |
| C12 | L | **Transação "sem sugestão"** (sem categoria) e pendente: como entra no consumido e na poupança? | O AD-6 só cobre o pendente *com* proposta. | Definir: fica fora de todos os termos e o checklist de fechamento a lista como pendência. |
| C13 | L | **Tema e tokens:** teste "no raw color" que quebra o build; rota `/dev/tema` só em local. | O AD-17 cobre os tokens e o `next-themes`. O AD-19 não cita o teste nem a rota. | Uma linha no AD-19 (lint/teste) e no AD-17 (rota de dev, protegida por env). Faixas de largura e drawers: o AD-17 já delega ao DESIGN.md, sem lacuna. |

## D. Regras do CLAUDE.md e das convenções

| Regra | Estado |
|---|---|
| Retorno só por XIRR | **Fraco.** Ver A4. |
| Nunca 5xx por falha de API externa | Ok (AD-15). |
| Binance só via cron | Ok (AD-18), coerente com o commit `453f8e1`. |
| Liquid com cliente dedicado | **Ausente.** Ver A3. |
| JWT próprio; access token fora do localStorage | **Só citado.** Ver A5. O código atual cumpre (`web/lib/auth.ts`). |
| **Rendimento de FII separado de ganho de capital em `asset_operations`** | **Ausente (M).** Proventos entram no caixa em corretora (FR-25: saídas + proventos − aplicado), no XIRR (fluxo positivo) e no adapter de movimentação B3. Correção: no AD-11 ou AD-13, operação tipada (`dividendo`/`rendimento`/`juros` ≠ `venda`), e o "resultado" por ativo separa provento de ganho de capital. |
| Chaves e TTLs de cache | Ok em parte: o formato da chave está certo; os TTLs foram "para `config.py`". Falta a chave de XIRR por período (A4). |
| `.env`/`.env.example`/gitleaks | Ok (AD-18). Os logs estão mais fracos que a regra (A8). |
| Gates m0–m7 do CLAUDE.md | **L.** O CLAUDE.md segue com a tabela de milestones e a stack da v1, incluindo deploy e Upstash. Atualizar o CLAUDE.md junto com a atualização do `conventions.md` na primeira story, citando o ADR-014. |

## E. Higiene (L)

- O diagrama mostra `workers → closing` apenas, mas os workers chamam `market`, `wallet` e
  `portfolio`. Desenhar os workers como casca fora das camadas, com acesso a todos os services.
- Os pacotes existentes `engines/analytics` (vazio) e `engines/jobs` (`/jobs/refresh`) não estão
  mapeados. Dizer se somem ou se viram `workers`.
- O EXPERIENCE › Termos do mês ainda traz as fórmulas antigas: consumido como `[ASSUMPTION]` e
  financiado = mín(resgates, consumido) = R$ 4.487,99. O spine segue o party mode
  (R$ 2.994,77), o que está certo, mas deveria registrar que essa seção do EXPERIENCE foi
  superada, para ninguém implementá-la.
