---
title: "Review — reconciliação do spine × PRD/brief/party mode"
target: ../ARCHITECTURE-SPINE.md
inputs:
  - ../../../prds/prd-goodies-2026-10-17/prd.md
  - ../../../prds/prd-goodies-2026-10-17/addendum.md
  - ../../../briefs/brief-goodies-2026-10-17/brief.md (+ addendum)
  - ../../../../party-mode/2026-10-17-abertura-arquitetura.md (prevalece sobre o PRD)
date: 2026-10-17
---

# Reconciliação do spine com PRD, brief e party mode

## Veredito

O spine cobre bem a espinha do produto: camadas, ingestão por adapter, AD-7 com uma função por
termo, o resumo congelado, avisos por providers, distribuição do aporte e tolerâncias. Mas ele
**não governa três fatos que os épicos dos marcos 1 e 3 vão precisar gravar**:

- as posições do consolidado B3;
- o saldo informado (LEDGERBAL) e a âncora do saldo calculado;
- o momento em que as operações derivadas são recalculadas depois da revisão.

Também ficam abertas as precondições do fechamento, e há duas regras que se contradizem por dentro:

- a camada onde mora "a caminho";
- o invariante de poupança diante do Repasse.

Precisa de uma rodada de correções antes de `bmad-create-epics-and-stories`.

## Cobertura FR → spine

| FR | Situação | Nota |
| --- | --- | --- |
| FR-1 | ok | `detect`; CSV via adapter Nubank. O aviso "CSV sem conferência" é ver F11 |
| FR-2 | parcial | prévia ok; o aviso "arquivo já importado" não tem fato persistido (F11) |
| FR-3 | parcial | "atualizado até" derivado ok; os limites (7 d, dia 15) não estão alocados (F19) |
| FR-4 | parcial | lacuna ok; "a caminho" está numa camada errada (F6) |
| FR-5 | **lacuna** | o saldo informado não é persistido e não há âncora do saldo calculado (F3) |
| FR-6 | ok/parcial | desfazer ok; o efeito de uma regra do lote fora do lote fica indefinido (F20) |
| FR-7 | parcial | fechamento retroativo ok; o mecanismo do fechamento em bloco conflita com AD-16 (F14) |
| FR-8 | parcial | grupos ok; a cópia de `kind` envelhece quando o grupo muda (F12) |
| FR-9 | parcial | pendentes e "sem sugestão" não estão definidos nas leituras (F9) |
| FR-10–FR-12 | ok | F21 (menor) |
| FR-13 | ok | `as_of` em AD-15 |
| FR-14 | parcial | avisos de evento × compute-on-read (F11) |
| FR-15, FR-16 | ok | — |
| FR-17 | ok | disponível sem devoluções + consumido líquido de devoluções, coerente com o party mode |
| FR-18 | ok | parâmetros do casamento fora de constantes (F19) |
| FR-19 | ok/parcial | AD-16 cobre; ADR-011 segue "vigente" no `decisions.md` (F5) |
| FR-20 | parcial | o tratamento de devoluções na taxa está indefinido (F7) |
| FR-21 | parcial | falta a guarda "sem custo por ativo cripto" (F13) |
| FR-22 | parcial | valor de início por classe/ativo (F18); exceção float do XIRR (F17); exclusão de RF/Cripto no mensal (F13) |
| FR-23 | ok | AD-5 + AD-11 (mas veja F2) |
| FR-24 | **lacuna** | o aporte de debênture depende da categoria confirmada, e a derivação roda antes da revisão (F2) |
| FR-25 | parcial | camada (F6) |
| FR-26 | **lacuna** | as posições do consolidado não são gravadas em lugar nenhum (F1) |
| FR-27 | ok | ADR-012 + `assets` |
| FR-28–FR-31 | ok | AD-12 fiel ao party mode; "investimento/realizado" bruto × líquido (F8) |
| FR-32 | parcial | sem precondições de fechamento (F4); "saldo conferido" depende de F3 |
| FR-33 | ok | — |
| FR-34 | parcial | a decomposição do patrimônio não fecha (F8) |
| FR-35 | parcial | o multiplicador e o alvo da reserva não estão alocados (F16) |
| FR-36 | ok | AD-17 |

| NFR / SM | Situação |
| --- | --- |
| Correção | parcial: F7 (invariante), F2 |
| Proveniência | parcial: linhas legadas e manuais sem lote (F15) |
| Resiliência | ok (AD-15) |
| Privacidade | parcial: CLAUDE.md/.env ainda apontam Supabase/Upstash (F5) |
| Desempenho | adiado com gatilho; sem medição (F23) |
| SM-2, SM-3 | dependem de F1, F3, F4 |
| SM-4 | ok (`is_manual`) |
| SM-5, SM-6, SM-C1 | **não mensuráveis** com o modelo atual (F10) |
| SM-C2 | parcial (F10) |
| SM-1 | comportamental; não exige arquitetura |

## Achados

### F1 — HIGH — Posições do consolidado B3 não são gravadas

- **Fonte:** FR-26, SM-3, AD-13 (conferência por quantidade), AD-8 (patrimônio retroativo vindo do
  consolidado), party mode §1/§5.
- **Problema:** hoje o consolidado só aplica preços (`b3_import_service.py`: "consolidado:
  preços aplicados"). Nenhuma tabela do Structural Seed guarda quantidade × ativo × mês de
  referência. Sem ela, AD-13 não tem contra o que comparar, e AD-8 não consegue montar o
  patrimônio retroativo.
- **Correção:** adicionar uma tabela `b3_position_snapshots`, dona `portfolio`, com `batch_id`,
  mês de referência, ativo, quantidade, preço e valor. AD-13 e AD-8 passam a referenciá-la.
  Declarar se o consolidado anual de dezembro cai na mesma tabela.

### F2 — HIGH — Derivações no `apply` acontecem antes da revisão

- **Fonte:** FR-24 ("só saídas com categoria de investimento em debênture viram aportes,
  sugeridos na revisão"), FR-9/FR-11 (corrigir e reaplicar), FR-6, AD-5 × AD-6.
- **Problema:** AD-5 manda gerar as operações de caixinha, RF e debênture no `apply`. Só que a
  categoria definitiva só existe depois de `ledger.categorize()`, na revisão. Corrigir, reaplicar
  uma regra ou recategorizar não recalcula as operações. Resultado: aporte fantasma ou faltante,
  XIRR errado e caixa em corretora errado.
- **Correção:**
  - A derivação passa a ser idempotente, por `transaction_id`.
  - Ela roda em `categorize()`, na mesma transação, e não no `apply`. A alternativa é derivar na
    leitura.
  - Definir o ciclo do "aporte sugerido de debênture": pendente → confirmado → removido quando a
    categoria muda.

### F3 — HIGH — Saldo informado e âncora do saldo calculado

- **Fonte:** FR-5, SM-2, FR-32 ("saldo conferido"), glossário "Saldo da conta".
- **Problema:** `plan` lê o saldo informado, mas nenhuma tabela o guarda (valor, data, conta,
  lote). Falta também a âncora do saldo calculado: saldo inicial por conta. A conta MEI só tem
  dados desde jan/2026 e a CPF desde jul/2024. AD-7 não tem a função "saldo calculado".
- **Correção:**
  - Persistir o LEDGERBAL por arquivo, em `import_batch_files` (F11) ou em
    `account_balance_checks`.
  - Definir a âncora: `accounts.opening_balance` + data, ou o primeiro LEDGERBAL.
  - Pôr `account_balance(conn, account, date)` no AD-7.

### F4 — HIGH — Precondições do fechamento indefinidas

- **Fonte:** SM-2/SM-3 ("em todo mês fechado bate"), UJ-5 ("fecha depois de conferir o saldo"),
  FR-9, FR-26.
- **Problema:** o spine não diz se dá para fechar um mês com transações pendentes ou sem
  categoria, saldo divergente, posição divergente ou dinheiro a caminho. As métricas primárias
  pressupõem que não.
- **Correção:** acrescentar ao AD-8 um de dois caminhos:
  - **bloquear** o fechamento nesses casos;
  - ou exigir uma confirmação explícita, gravada em `month_closes` (por exemplo
    `closed_with_issues`, com a lista).

  Em qualquer caso, a cobertura por fonte entra no snapshot, como já está.

### F5 — HIGH — ADRs e CLAUDE.md não são reconciliados

- **Fonte:** PRD §8 (ADR-011 revertido; os demais ADRs e o CLAUDE.md continuam valendo), AD-18.
- **Problema:**
  - O CLAUDE.md manda "não violar" o `decisions.md`, e lá o ADR-011 (resgate = investment
    líquido) continua ativo. Isso contradiz FR-19 e AD-16.
  - O CLAUDE.md ainda fixa Supabase, Upstash e Fly/Vercel ("não mudar sem ADR"), enquanto AD-18
    roda tudo local.
  - Com `DATABASE_URL`/`REDIS_URL` apontando para a nuvem, `xirr:consolidated` e as transações
    sairiam do ambiente, violando NFR-privacidade.
- **Correção:** uma AD, ou uma linha nas Consistency Conventions igual à do `conventions.md`,
  dizendo que a 1ª story:
  - marca o ADR-011 como *superseded*;
  - registra um ADR "v2.0 local" (Postgres e Redis em docker; proibido host Supabase/Upstash na
    v2.0);
  - atualiza o CLAUDE.md.

### F6 — MEDIUM — "A caminho" e caixa em corretora na camada errada (contradição interna)

- **Fonte:** AD-7 × AD-1, FR-25, FR-4. O código atual tem `portfolio/transit.py`.
- **Problema:** AD-7 põe "a caminho" em `planning/calc` (camada 4). Mas o patrimônio
  (`portfolio/calc`, camada 3) inclui o caixa em corretora, que depende da mesma classificação
  coberto × a caminho. O aviso "transferência não coberta" também sai de baixo. Do jeito que
  está, ou portfolio importa planning (violando AD-1) ou a regra é duplicada (violando AD-7).
- **Correção:** levar `in_transit` e `broker_cash` para `portfolio/calc`. `planning` só os
  consome para o realizado e o pendente.

### F7 — MEDIUM — Devoluções × taxa de poupança × invariante do AD-16 (contradição)

- **Fonte:** party mode §3 (Repasse sai de Trabalho e vai para Devoluções), FR-20, NFR-correção
  ("pré-jun/2026 só muda por FR-19"), AD-16 ("totais de poupança inalterados").
- **Problema:**
  - Mover o Repasse reduz a receita do trabalho nos meses que tiveram repasse. A taxa histórica
    muda, e só jun/2026 está imune. O invariante do AD-16 falha por construção.
  - Não está decidido se a taxa usa gastos brutos ou gastos − devoluções. O consumido desconta
    devoluções e a taxa não, o que é incoerente.
- **Correção:**
  - Definir explicitamente receita do trabalho = grupo Trabalho.
  - Definir a taxa de poupança: (trabalho − (gastos − devoluções)) / trabalho, ou manter bruto e
    aceitar a mudança.
  - Restringir o invariante ao gate de jun/2026 + deltas esperados por revisão.
  - Registrar que o party mode relaxa o NFR-correção (Cartão de crédito, Repasse, "Cripto
    Nubank").

### F8 — MEDIUM — Tabela do AD-7 incompleta

- **Fonte:** §3 (Resultado do mês, Receita, Aplicado, Valor atual, Resultado, Proventos, Caixa em
  corretora), FR-13, FR-34, addendum ("investido hoje é líquido de resgates → muda").
- **Faltam:**
  - resultado do mês;
  - receita total e gastos;
  - **investimento do mês** (bruto depois do FR-19? o realizado total é bruto?);
  - saldo calculado;
  - aplicado, valor atual e resultado;
  - progresso e necessidade de objetivo;
  - a **decomposição do crescimento do patrimônio** (FR-34). Δpatrimônio ≠ aporte + resultado,
    porque o patrimônio inclui o saldo das contas.
- **Correção:**
  - Completar a tabela.
  - Fixar investimento = saídas brutas (resgate é receita).
  - Definir a decomposição como aporte + resultado + Δsaldo das contas, ou redefinir "aporte"
    nesse uso.

### F9 — MEDIUM — Pendentes e "sem sugestão" nas leituras (tensão com §3)

- **Fonte:** §3 "Sugestão… nunca é aplicada sem confirmação", FR-9 "sem sugestão", AD-6
  `[ASSUMPTION]`, AD-16 "zero órfãs de `category_id`".
- **Problema:**
  - Contar o pendente com a categoria proposta é, na prática, aplicar a sugestão nas leituras.
  - Uma transação "sem sugestão" não tem `category_id` nem `kind`, então não se sabe em que
    total ela entra, e ela fere o "zero órfãs".
- **Correção:**
  - Ratificar a suposição com o Vitor e marcar as leituras com pendências (`provisional: true`
    junto do `as_of`).
  - Criar a categoria-sentinela "Sem categoria" por tipo, inferido pelo sinal, e contá-la à parte.
  - Ligar com F4.

### F10 — MEDIUM — SM-5, SM-6, SM-C1 e SM-C2 não são mensuráveis

- **Fonte:** §7.
- **Problema:** `category_source` é sobrescrito quando o Vitor corrige. Não há registro da origem
  inicial, da confirmação nem de correção depois de confirmada. Para a SM-C2 falta saber se a
  condição dispensada se resolveu.
- **Correção:**
  - Criar `categorization_events`, append-only e dona `ledger` (tx, de, para, origem, lote, em),
    ou as colunas `initial_source`, `confirmed_at` e `corrected_after_confirm`.
  - Dar `dismissed_at` a `alert_dismissals`.
  - Acrescentar as SMs a `binds`.

### F11 — MEDIUM — Avisos de evento × compute-on-read; lote com várias fontes

- **Fonte:** FR-2 ("arquivo já importado"), FR-1 ("CSV sem conferência"), FR-14 ("some sozinho"),
  AD-5 (`import_batches` com período "por fonte e conta").
- **Problema:**
  - Esses avisos são eventos, sem uma condição persistente da qual derivar, e o spine não define
    quando somem.
  - Um lote pode ter vários arquivos de fontes diferentes, e uma linha de `import_batches` não
    guarda um período por fonte.
- **Correção:**
  - Criar `import_batch_files` (lote, fonte, conta, hash do arquivo, formato, período, saldo
    informado). A cobertura e as lacunas passam a ser derivadas daí.
  - Definir: "arquivo já importado" é mensagem da prévia, ou aviso que expira em N dias;
    "CSV sem conferência" vale enquanto o último arquivo da conta for CSV.

### F12 — MEDIUM — A cópia de `kind` envelhece

- **Fonte:** FR-8 (editar grupo e subcategoria), AD-6 (`kind` gravado só por `categorize()`).
- **Problema:** mudar o tipo de um grupo, ou mover uma subcategoria de grupo, deixa
  `transactions.kind` divergente e altera totais de meses fechados.
- **Correção:**
  - A edição recategoriza as linhas afetadas na mesma transação e conta como "ajuste em mês
    fechado".
  - Ou proibir trocar o tipo de um grupo com transações.

### F13 — MEDIUM — Faltam as guardas do bloco cripto e da rentabilidade mensal

- **Fonte:** §3 Bloco cripto, §5 não-objetivo, FR-22 ("mensal por ativo, exceto RF e Cripto"),
  memória "Tier 2 guardado, não exibido".
- **Problema:** o spine lista `crypto_cost_basis` (custo por ativo) como tabela de `wallet`, mas
  não diz que ela nunca é exposta.
- **Correção:** invariante, numa AD ou no AD-7:
  - nenhum `models.py` emite aplicado, resultado ou rentabilidade por ativo cripto;
  - a rentabilidade mensal por ativo exclui RF e Cripto.

### F14 — MEDIUM — Fechamento em bloco jul/2024–mai/2026 (contradição AD-16 × AD-8)

- **Fonte:** FR-7, AD-8 (`build_month_summary` é a única forma de calcular), AD-16 (dados em SQL
  dentro do Alembic), party mode §4 ("dívidas do mês pré-preenchidas nos retroativos").
- **Problema:** fechar em SQL dentro de uma migração duplica o cálculo. Também não se diz quem
  preenche `month_plans` dos meses históricos (dívidas e aporte planejado), uma tabela de outra
  engine, num fechamento.
- **Correção:**
  - O fechamento em bloco é um comando de `closing.service`, idempotente e rodado depois da
    migração.
  - O preenchimento de `month_plans.debts` é feito por `planning.service`.
  - Definir o aporte planejado histórico: nulo, com pendente "n/d".

### F15 — MEDIUM — Proveniência das linhas legadas e manuais

- **Fonte:** NFR-proveniência ("toda transação e operação sabe de qual lote e fonte veio").
- **Problema:** as ~1.454 transações e as operações atuais não têm `batch_id`. Lançamentos de
  Hermes e manuais também não.
- **Correção:**
  - No AD-16, criar um lote `legado` por fonte e conta, com o período real.
  - Usar `source ∈ {manual, hermes}` para linhas sem arquivo.
  - Garantir que o lote legado não gere lacunas falsas.

### Menores (LOW)

- **F16:** não estão governados:
  - a conversão "Médio Prazo → objetivo Snow Trip";
  - a semente de `goals` (Reserva, Snow Trip);
  - o alvo da reserva = multiplicador × custos fixos (derivado ou gravado?) e onde mora o
    multiplicador (FR-35).
- **F17:** o XIRR usa float (`brentq`). AD-4 proíbe float em dinheiro e não abre a exceção para a
  taxa calculada pelo solver.
- **F18:** o valor de início (FR-22) precisa vir por classe e por ativo de `month_summary_lines`,
  não só do patrimônio total.
- **F19:** os limites de defasagem (FR-3) e os parâmetros do casamento de custo fixo (FR-18:
  ±10%, ±5 d, 3 d) não estão alocados como constantes de `calc.py`, como o AD-13 faz.
- **F20:** desfazer um lote cuja regra recategorizou transações fora dele (prévia do FR-10): o
  que acontece com essas transações?
- **F21:** a reaplicação (FR-11) sobrescreve uma "sugestão confirmada"? O FR-12 a distingue; o
  AD-6 só protege `manual`.
- **F22:** "nunca executa": exigir chaves Binance/exchange somente leitura (AD-18).
- **F23:** NFR-desempenho de 3 s: o adiamento tem gatilho, mas não há medição. Sugestão: um teste
  de tempo do painel com a base real.
- **FR-7 × party mode:** o PRD diz que os meses recuperados "começam abertos" e são fechados pelo
  Vitor; o party mode diz que o assistente fecha. O AD-8 deve dizer qual dos dois (assistente com
  confirmação por mês).

## Contradições spine × entradas (fora as que o party mode autoriza)

1. **AD-6:** a suposição "pendente conta com a proposta" × §3 Sugestão (F9).
2. **AD-16:** o invariante "poupança inalterada" × o Repasse em Devoluções, decidido no party
   mode (F7).
3. **AD-7 × AD-1:** "a caminho" em `planning`, mas é necessário em `portfolio` (F6).
4. **AD-16 × AD-8:** como fazer o fechamento em bloco (F14).
5. **AD-18 × CLAUDE.md/ADR-011:** não reconciliados (F5).

Conferidos e **coerentes**: AD-12 (party §2), AD-13 (party §5), AD-7 consumido, disponível e
financiado (party §4), AD-11 (Q1), AD-8 (versões e retroativo). A Flash fora do hub segue o PRD
(FR-24 abre mão do import), que prevalece sobre o brief.

## Deixado de fora de propósito (nível de story)

Texto e ação de cada aviso, as fórmulas exatas do déficit monotônico, o método do "maior resto"
por objetivo, o layout das abas e drawers, a explicação de "saldo divergente" (transações
candidatas), a média de 12 meses e o destaque de melhor desempenho, a validação "preço manual só
sem fonte", travas acima do planejado.
