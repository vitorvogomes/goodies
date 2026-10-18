---
title: "Prontidão para implementação — Goodies v2.0"
date: 2026-10-18
verdict: PASS (após correções)
inputs:
  - prds/prd-goodies-2026-10-17/prd.md
  - architecture/architecture-goodies-2026-10-17/ARCHITECTURE-SPINE.md
  - ux-designs/ux-goodies-2026-10-17/DESIGN.md
  - ux-designs/ux-goodies-2026-10-17/EXPERIENCE.md
  - epics.md
---

# Prontidão para implementação — Goodies v2.0

**Veredito: CONCERNS.** Três revisões independentes (rastreabilidade, implementabilidade contra o código, dependências e
segurança de dado) chegaram ao mesmo veredito. O **Épico 1 pode começar**. As stories dos Épicos 2, 3, 5, 6 e 7 que
mexem em dado real precisam das correções abaixo antes de serem implementadas. Os achados graves foram conferidos no
código (`transit.py:70-75`, `caixinhas.py:72-76`, `bcb.py:85`, `api/Dockerfile`).

## A. Decisões de produto e dado (do Vitor)

| # | Decisão | Onde | Recomendação |
|---|---|---|---|
| D1 | Pagamento em Dívidas num mês **ao vivo** com "Dívidas do mês" = 0 sai do consumido e não entra no disponível: o restante fica inflado | AD-7, party mode §4, Story 6.4 | Pré-preencher "Dívidas do mês" também ao vivo com Σ role `divida` não casada (editável) |
| D2 | Taxa de poupança: PRD/EXPERIENCE usam (trabalho − gastos)/trabalho; AD-7 e stories descontam devoluções. Com Repasse em Devoluções, a taxa histórica muda nos meses com repasse (o FR-19 promete que não muda) | PRD FR-19/FR-20, EXPERIENCE, AD-7 | Confirmar a fórmula com devoluções, emendar PRD/EXPERIENCE e listar os deltas por mês no script de comparação |
| D3 | Âncora do saldo PF em jun/2026 é tautológica (o mês da âncora sempre "confere") e o legado não guardou `LEDGERBAL` | Story 3.11 | Reimportar os OFX mensais da PF desde jun/2024 (0 transações novas, grava o saldo) e ancorar no mais antigo: a conferência passa a valer em todos os meses, inclusive os do bloco |
| D4 | O aviso de ajuste em mês fechado deveria mostrar a diferença ao vivo − congelado (party mode); EXPERIENCE e Story 5.5 mostram só "não mudou" | party mode §1, EXPERIENCE, Story 5.5 | Mostrar a diferença na mensagem ("Lazer passaria de R$ 812 para R$ 870") |
| D5 | Defasagem do MEI: limite de 7 dias vira ruído, porque o OFX do MEI é anual/multi-mês | FR-3, Story 3.8 | MEI fora dos 7 dias; aviso só se o mês anterior não estiver coberto até o dia 15 |
| D6 | Entrada vinda de Binance/Liquid/corretora cripto de volta ao Nubank é resgate? | ADR-015, Story 2.5 | Sim: resgate do bloco cripto (mesma regra de caixinha/corretora) |
| D7 | Data de referência do consolidado B3 e período dos xlsx de movimentação/negociação não estão no conteúdo do arquivo | Stories 3.7, 3.8 | Tirar do nome do arquivo (mensal → fim do mês; anual → 31/12) e mostrar na prévia para o Vitor confirmar ou corrigir |
| D8 | Cripto no fim de jun–set/2026 para o fechamento pelo Assistente: não há histórico de carteira | Stories 5.1, 5.7 | Mesma regra do retroativo: aplicado do bloco, cobertura "estimada" |

## B. Correções técnicas (sem decisão de produto)

**Segurança de dado (alta)**
- **T1 — Resgates pareados por trilho (2.5, 3.4, 7.3).** `transit._saiu`, `crypto_sleeve` e `caixinhas.build_caixinha_ops`
  netam os resgates pela categoria de investimento. Registrar o par `invest:x` ↔ `resgate:x` por trilho e fazer os três
  leitores lerem as duas keys; invariante na 2.5: XIRR, trânsito, bloco cripto e `build_caixinha_ops` iguais antes e depois.
- **T2 — Caixinhas curadas protegidas (3.4, 7.3).** `transaction_id` preenchido pelo `external_id`
  (`caixinha:{sym}:{fitid}`); ops curadas (`caixinha-yield:*`, ajuste Turbo −R$ 123,91, bucket Nubank-Encerradas)
  marcadas protegidas; a rederivação nunca apaga op sem `transaction_id`; invariante de net/aplicado/XIRR por ativo.
- **T3 — Debêntures sem duplicar (7.4).** As 12 integralizações já estão em `asset_operations`: ligar a `debentures`/
  `assets` sem reinserir; sugerir aporte só para transação sem op; invariante aplicado Flash = R$ 12.000,00.
- **T4 — Desfazer completo (3.12, 6.1).** `fixed_cost_payments` com FK `ON DELETE CASCADE` (ou hook `on_batch_undo` do
  ledger); o desfazer remove também `account_balances`, `broker_position_snapshots` e `import_batch_files` do lote e
  recalcula a âncora; teste de regressão na 6.1.
- **T5 — Regras com sentido (2.3, 3.3).** `category_rules.direction ∈ {entrada, saida, ambos}` (os padrões `caixinha`,
  `rdb`, `dinheiro guardado` casam aplicação e resgate); o detector de transferência interna (`importer.py:115-116`,
  `LEDGER_SELF_IDENTIFIERS`) fica no adapter Nubank.
- **T6 — Mapa explícito das 33 categorias (2.2, 2.4).** Tabela (nome, `kind`) → subcategoria na story, incluindo
  `income` gravado em "outros" e estornos positivos em gasto; a fusão Flash Capital/Betuel → Recorrente entra como delta
  esperado (o texto "totais idênticos" vira "idênticos salvo deltas listados").
- **T7 — Histórico de CDI e IPCA (7.2, 7.3).** `bcb.py` só busca `ultimos/1`: buscar por intervalo
  (`dataInicial`/`dataFinal` do SGS) e fazer backfill desde jun/2024.

**Dependências e infraestrutura (média)**
- **T8 — Kit comum do backend.** `common.owner`, `common.money` (`Money`, `Pct`), `common.models.Valued`, `common.deps`,
  `common.cache` (com a invalidação do XIRR) e `MonthStatusPort` (padrão "todos abertos") nascem numa story nova no início
  do Épico 2; as stories 2.4/2.8 já chamam `mark_dirty`.
- **T9 — Dependências para a frente.** Precondições do fechamento (5.2) por registro: posição divergente e a caminho
  entram quando os Épicos 7 nascem; trocar 7.1 ↔ 7.2 (`build_period_summary` antes da leitura em Posições); em 6.5 a
  legenda "não definido" não linka para Aportes até a 8.4.
- **T10 — Backup antes de toda escrita de dado.** Guarda no `env.py` do Alembic (exige backup recente fora do banco de
  teste) e backup no início de `close_retro`, `refechar` e rederivações.
- **T11 — AD-16 em toda story de dado.** Invariante + idempotência explícitos em 3.4, 3.11, 7.3, 8.2 e 10.5.
- **T12 — Transação sem lote.** Lançamento manual e Hermes: `source ∈ {manual, hermes}` com `batch_id` nulo permitido; o
  invariante da 2.1 vale para linhas importadas.
- **T13 — Esquema duplo até a 10.5.** `categorize()` grava também a coluna de texto até ela sair; a 10.5 remove
  `match_patterns`.
- **T14 — Numeração.** Stories não cravam número de revisão (só a ordem da AD-16); `close_retro` exige `head`.
- **T15 — `job_runs.last_success_at`** (4.3).
- **T16 — Banco próprio para dados reais.** `goodies_test` é da suíte unitária; os testes `dados_reais` usam
  `goodies_dados` (1.2).
- **T17 — Lacunas de ambiente.** `pg_dump` 15 na imagem da api (1.2); `python-multipart` (3.3); Vitest + script `test`
  no web (1.5/1.7); seletor de conta no CSV (3.6); contas pelo `account_number` (3.4).
- **T18 — Stories grandes.** Dividir 5.1 (histórico de preço + movimentos de market × resumo ao vivo) e 7.3 (backfill e
  valoração pelo CDI × derivação por hooks).
- **T19 — Snapshot completo.** ACs em 7.2, 7.5 e 8.7 ligando os termos novos ao `build_month_summary`, com o golden
  "snapshot = ao vivo".

**Acabamento (baixa)**
- **T20.**
  - "Falha ao gravar" nas stories 2.7, 3.9, 3.12, 5.4, 6.1, 6.5 e 8.6.
  - Termo "restante sem resgates" em `planning/calc`.
  - Linhas de caixa em corretora e a caminho em Posições (7.5).
  - Critério das transações candidatas: desde o último saldo conferido (3.11).
  - Média 12m no gráfico de aporte (9.3).
  - Mensagens de aviso de scan e de worker no catálogo.
  - Telas v1 por link dentro das áreas, não como abas (1.6, AD-17).
  - `asset_aliases` e as sugestões de debênture no mapa de donos.
  - Ordem de precedência da AD-1: atribuição explícita vence "primeira story que tocar".
  - `valid_from` do backfill de custos fixos ≤ jul/2024 (6.1).
  - Soma de metas por rota de prévia (8.2).
  - `portfolio_targets.asset_id` nulo, com o mapa de rótulos de classe (3.2).
  - Leitura transitória do Painel antes de `closing` documentada (4.1).

## C. Emendas nos documentos de origem

- **PRD:** FR-19 (deltas de poupança nos meses com repasse), FR-20 (fórmula com devoluções), glossário (disponível =
  trabalho + resgates…; progresso do objetivo = valor atual dos ativos).
- **EXPERIENCE:** consumido e consumo financiado sem `[ASSUMPTION]` (R$ 2.994,77), taxa de poupança, mensagem de ajuste
  com a diferença, defasagem do MEI.
- **Spine:** T1 (par investimento ↔ resgate por trilho), T5 (`direction`), mapa de donos, precedência da AD-1.

## Próximo passo

Resolver D1–D8, aplicar B e C em `epics.md` e nos documentos de origem (com linha no memlog de cada um) e rodar esta
checagem de novo. Depois: revisão adversarial e `bmad-correct-course` (PROGRESS.md e `/story`, `/done`, `/gate` em
`docs/v2/`).

## Resolução (2026-10-18)

- O Vitor aprovou D1–D8 como recomendados. B (T1–T20) e C foram aplicados em `epics.md` (agora **70 stories**:
  novas 2.1 Base comum do backend, 5.1 Histórico de preço e 7.4 Caixinhas e CDBs derivados), no PRD, no EXPERIENCE,
  no spine (lint sem apontamentos) e no party mode, com linha no memlog de cada um.
- **Re-checagem independente:** 26 itens resolvidos e 3 parciais; nenhum achado alto. Os parciais e os 4 achados novos
  foram corrigidos em seguida:
  - FR19/2.6 coerentes com D2;
  - stories sem número de revisão cravado;
  - "Dívidas do mês" pré-preenchido no EXPERIENCE;
  - receita do trabalho sem devoluções no glossário;
  - `ancorar_saldo` em modo só-saldo, ancorado no fim de jul/2024;
  - RF pelo método vigente no resumo ao vivo;
  - chave de fallback das caixinhas e o bucket das encerradas;
  - AD-7 e AD-8 do spine;
  - UX-DR30 na 7.5;
  - as duas mensagens novas no catálogo.
- **Veredito final: PASS.** Os Épicos 1 e 2 podem começar.
