# Goodies — Progress Tracker

> Substituição do GSD-Pi para rastreamento de estado entre sessões do Claude Code.
> Claude Code atualiza este arquivo ao concluir cada story.
> Para iniciar uma sessão: "Read CLAUDE.md and PROGRESS.md, then continue from the next pending story."

---

## Como usar

**Iniciar sessão no Claude Code:**
```
Read CLAUDE.md and PROGRESS.md. Continue from the next IN_PROGRESS or PENDING story.
Implement following TDD. Update PROGRESS.md when done.
```

**Status:**
- `[ ]` PENDING — ainda não iniciada
- `[~]` IN_PROGRESS — em andamento (sessão atual)
- `[x]` DONE — concluída e commitada
- `[!]` BLOCKED — bloqueada por dependência

---

## Milestone m0 — Foundation

| # | Story | Status | Commit |
|---|---|---|---|
| 00-01 | Criar monorepo e estrutura de pastas | [x] | ac75de3 |
| 00-02 | Setup FastAPI com health check | [x] | 2010eae |
| 00-03 | Conectar Supabase (Postgres pool + schema users) | [x] | d54e849 |
| 00-04 | Conectar Redis (Upstash) | [x] | 0cb36ca |
| 00-05 | Implementar auth JWT (login, refresh, middleware) | [x] | a8da1c9 |
| 00-06 | Setup Next.js com TypeScript e Tailwind | [x] | ff397a2 |
| 00-07 | Tela de login no frontend | [x] | b58050e |
| 00-08-09 | GitHub Actions + Deploy Fly.io e Vercel | [~] | — |

**Gate m0:** `GET /api/v1/health` → 200 com Postgres + Redis. Login funciona.

---

## Milestone m1 — Ledger Engine

| # | Story | Status | Commit |
|---|---|---|---|
| 01-01 | Schema de banco (accounts, transactions, fixed_costs, monthly_summary view) | [x] | 81a1a51 |
| 01-02 | CRUD de contas e categorias | [x] | 9d588d8 |
| 01-03 | CRUD de transações com validação | [x] | c8bfdd5 |
| 01-04 | Cálculo de saldo running e resumo mensal | [x] | 97aed78 |
| 01-05 | Cálculo de taxa de poupança | [x] | 97aed78 |
| 01-06 | Projeção de caixa 30/60/90 dias | [x] | afb2a9f |
| 01-07 | CRUD de custos fixos | [x] | da7da3f |
| 01-08 | Alertas de vencimento e categoria acima de 120% | [x] | eb78d02 |
| 01-09 | Endpoints Hermes (POST /expenses, POST /income) | [x] | 4f4a161 |
| 01-10 | Frontend — lista de transações + filtros | [x] | 870a2ae |
| 01-11 | Frontend — formulário de nova transação | [x] | 442e81e |
| 01-12 | Frontend — dashboard de caixa | [x] | eecc831 |
| 01-13-14 | Migração + validação extrato Nubank (OFX/CSV) | [x] | e27ba29 |
| 01-15 | Frontend — análise por categoria + gestão de categorias + custos recorrentes | [x] | d757eaf |

**Gate m1:** **✅ CONSOLIDADO**. Engine **kind-aware** (refator): o import grava TODO movimento com `kind` (income/expense/investment/transfer) — investimento conserta o saldo (não some) mas fica fora do consumo; `savings_rate=(receita−consumo)/receita` (B, canônica) + `investment_rate=investido/receita` (A, KPI bônus). Destinos configuráveis via `categories.match_patterns`. Decisão final em 2026-06-04: `LEDGER_SELF_IDENTIFIERS` = **só o CNPJ do MEI** (`47.272.354/0001-59`) — nome/CPF são amplos demais (casavam Santander pessoal no mesmo nome, marcando-a como interna); Santander pessoal agora conta como receita/despesa externa (usuário: "é externa mesmo"). Nº de conta Nubank (CPF `4288917-8`, CNPJ `58022571-6`) já automático. Reimpor exige `DELETE FROM transactions` + `scripts/reset_ledger.py --yes`. Mecanismo validado com dados reais jan–jun/2026 (320 tx): 5 destinos classificados, investimentos fora do saldo fantasma, Santander externo, saldo R$ 3.386,75, poupança(B) estabilizada 22–40%/mês. Dados e engine coerentes; prontos p/ bridge m1↔m2.

---

## Milestone m2 — Portfolio Engine

| # | Story | Status | Commit |
|---|---|---|---|
| 02-01 | Schema de banco (asset_operations, portfolio_targets, positions view) | [x] | d7ccf5b |
| 02-02 | Seed portfolio_targets (alvos do Vitor) | [x] | f71bfc2 |
| 02-03 | CRUD de operações com validação de tipos | [x] | 67cf200 |
| 02-04 | Cálculo de preço médio ponderado (DCA) | [x] | 1893c7f |
| 02-05 | **XIRR — implementação e testes (gate crítico)** | [x] | f71bfc2 |
| 02-06 | Endpoint XIRR por ativo e consolidado | [x] | b8c8c0e |
| 02-07 | Posição atual por ativo (valor com preço manual) | [x] | b8c8c0e |
| 02-08 | Cálculo de alocação atual vs. meta + desvio | [x] | 642110d |
| 02-09 | Motor de rebalanceamento | [x] | ee6e30e |
| 02-10 | Rastreamento de rendimentos separado (FII, JCP) | [x] | 3d8886c |
| 02-11 | Estimativa de IR por categoria | [x] | 75367c4 |
| 02-12 | IR cripto: consolidação mensal + alerta 80% | [x] | e4a1c59 |
| 02-13 | Frontend — tabela de posições | [x] | 2bba8e1 |
| 02-14 | Frontend — histórico de operações | [x] | 2bba8e1 |
| 02-15 | Frontend — alocação vs. meta (pizza chart) | [x] | 2bba8e1 |
| 02-16 | Frontend — tela de rebalanceamento | [x] | 2bba8e1 |
| 02-17-18 | **Migração + validação XIRR (gate crítico)** | [x] validado vs planilha: custo 99,95%, qtd exata, valores exatos; XIRR 15,25% | (gate) |

**Gate m2:** XIRR Python == Excel XIRR nos dados históricos (±0,1 pp).
**Status m2: 17/17 ✅** — gate validado por reconciliação contra a planilha DESEMPENHO CARTEIRA (a planilha não tem célula única de XIRR; tem %Variação por ativo). Custo total 99,95% (meu R$22.440,64 vs planilha R$22.451,21), quantidades exatas (ex.: NASD11 29=29 cotas — onde o custo difere, o sistema é MAIS preciso, usa o preço real da B3 vs médio defasado da planilha), valores atuais alinhados. **XIRR consolidado = 15,25% a.a.** (B3+Tesouro+Flash). Follow-ups menores: aporte do CDB Guanabara (precisa da data + fórmula CDI), refino fracionário do Tesouro, cripto (m4).

---

## Milestone m3 — Market Data

| # | Story | Status | Commit |
|---|---|---|---|
| 03-01 | Schema asset_prices + interface de cache Redis | [ ] | — |
| 03-02 | Fetcher BRAPI.dev (B3) com retry | [ ] | — |
| 03-03 | Fetcher CoinGecko (cripto) | [ ] | — |
| 03-04 | Fetcher Tesouro Direto com matching flexível | [ ] | — |
| 03-05 | Worker price_b3 (cron dias úteis 4h) | [ ] | — |
| 03-06 | Worker price_crypto (cron 2h) | [ ] | — |
| 03-07 | Lógica de fallback (Redis → Postgres → manual) | [ ] | — |
| 03-08 | Endpoint de update manual de preço | [ ] | — |
| 03-09 | Endpoints de leitura de preços | [ ] | — |
| 03-10 | Portfolio Engine usando preços do Market Engine | [ ] | — |
| 03-11 | Frontend — tela de preços com staleness indicator | [ ] | — |
| 03-12 | Testes de integração dos fetchers (mocks) | [ ] | — |

**Gate m3:** preços atualizando sem erro por 48h.

---

## Milestone m4 — Broker Integration

| # | Story | Status | Commit |
|---|---|---|---|
| 04-01 | Schema wallet_positions + worker scaffold | [ ] | — |
| 04-02 | Fetcher Etherscan (ETH/ARB/HYPE) | [ ] | — |
| 04-03 | Fetcher Solscan (SOL) | [ ] | — |
| 04-04 | **Fetcher Liquid Network (client dedicado — ADR-005)** | [ ] | — |
| 04-05 | Fetcher Binance API (spot + earn) com HMAC | [ ] | — |
| 04-06 | Worker wallet_scan cron 3×/dia + fallback | [ ] | — |
| 04-07 | Worker benchmark_daily (BCB + yfinance) | [ ] | — |
| 04-08 | Entrada manual DeFi (Phantom) + alerta vencimento | [ ] | — |
| 04-09 | Alertas de vencimento DeFi (30d e 7d) | [ ] | — |
| 04-10 | Frontend — tela de wallets | [ ] | — |
| 04-11 | Frontend — reconciliação posição escaneada | [ ] | — |
| 04-12 | Testes de integração (mocks chain explorers) | [ ] | — |

**Gate m4:** posições cripto escaneadas automaticamente.

---

## Milestone m5 — Analytics

| # | Story | Status | Commit |
|---|---|---|---|
| 05-01 | Schema benchmark_data + goals + active_alerts | [ ] | — |
| 05-02 | Importação histórica BCB (CDI/IPCA jul/2024→hoje) | [ ] | — |
| 05-03 | Importação histórica IBOV (yfinance) | [ ] | — |
| 05-04 | Cálculo de benchmarks acumulados no período | [ ] | — |
| 05-05 | Retorno real (nominal − inflação) | [ ] | — |
| 05-06 | Drawdown máximo histórico | [ ] | — |
| 05-07 | Projeção em 3 cenários (fórmula de anuidade) | [ ] | — |
| 05-08 | Seed de metas (Reserva R$50.872, LF R$1.271.802) | [ ] | — |
| 05-09 | Prazo estimado para metas | [ ] | — |
| 05-10 | **Engine de alertas (6 tipos)** | [ ] | — |
| 05-11 | Alerta de rebalanceamento (≥ 2pp) | [ ] | — |
| 05-12 | Alerta concentração Flash | [ ] | — |
| 05-13 | Worker alert_eval (cron diário 8h) | [ ] | — |
| 05-14 | Endpoints analytics (summary, benchmarks, projection, goals) | [ ] | — |
| 05-15 | Endpoints Hermes (resumo-geral, alertas) | [ ] | — |
| 05-16 | Endpoint GET /alertas + PUT /read | [ ] | — |
| 05-17 | Frontend — XIRR vs benchmarks (gráfico linha) | [ ] | — |
| 05-18 | Frontend — projeções 3 cenários (gráfico área) | [ ] | — |
| 05-19 | Frontend — metas com progress bar | [ ] | — |
| 05-20 | Frontend — card de alertas no dashboard | [ ] | — |

**Gate m5:** CDI/IPCA/IBOV no dashboard. Alerta concentração Flash ativo.

---

## Milestone m6 — Observability

| # | Story | Status | Commit |
|---|---|---|---|
| 06-01 | Configurar structlog (JSON produção, colorido dev) | [ ] | — |
| 06-02 | Instrumentar fetchers de API com logs de duração | [ ] | — |
| 06-03 | Instrumentar workers (início, fim, duração) | [ ] | — |
| 06-04 | Integrar Sentry SDK | [ ] | — |
| 06-05 | Alertas de sistema para Discord via webhook | [ ] | — |
| 06-06 | Rate limiting com slowapi | [ ] | — |
| 06-07 | Health check detalhado | [ ] | — |
| 06-08 | Testes de falha (Redis down, API down) | [ ] | — |

**Gate m6:** falha de worker notifica Discord < 5min.

---

## Milestone m7 — Frontend

| # | Story | Status | Commit |
|---|---|---|---|
| 07-01 | Layout global (sidebar, header, sistema de rotas) | [ ] | — |
| 07-02 | Dashboard principal | [ ] | — |
| 07-03 | Ledger UI — lista de transações com filtros | [ ] | — |
| 07-04 | Ledger UI — formulário de transação | [ ] | — |
| 07-05 | Ledger UI — resumo mensal e projeção | [ ] | — |
| 07-06 | Portfolio UI — tabela de posições | [ ] | — |
| 07-07 | Portfolio UI — alocação e rebalanceamento | [ ] | — |
| 07-08 | Portfolio UI — histórico de operações | [ ] | — |
| 07-09 | Market UI — preços com staleness | [ ] | — |
| 07-10 | Analytics UI — XIRR vs benchmarks | [ ] | — |
| 07-11 | Analytics UI — projeções e metas | [ ] | — |
| 07-12 | Loading states e error states globais | [ ] | — |
| 07-13 | Revisão de acessibilidade | [ ] | — |
| 07-14 | Validação final: 30 dias sem planilha | [ ] | — |

**Gate m7:** Vitor usa o Goodies como única fonte de verdade por 30 dias.

---

## Registro de sessões

| Data | Milestone | Stories completadas | Notas |
|---|---|---|---|
| — | — | — | Início do desenvolvimento |
| 2026-06-03 | m0 | STORY-00-01 | Scaffolding monorepo (api/, web/, .github/, fly.toml, pyproject, pre-commit ruff+eslint). |
| 2026-06-03 | m0 | STORY-00-02 | FastAPI + GET /api/v1/health (200), config via pydantic-settings, health check plugável (registro p/ 00-03/00-04), Dockerfile + docker-compose (Postgres+Redis), requirements pinados, teste httpx. Verificado: pytest/ruff/mypy + container 200. |
| 2026-06-03 | m0 | STORY-00-06 | Next.js 16 + React 19 + Tailwind v4 (ADR-009, atualiza ADR-001). lib/api (fetch+Bearer+cookie), lib/auth (token em memória), types/{health,auth}, React Query v5 + next-themes (dark), tema com tokens gain/loss/warning, page→/login. Verificado: pnpm lint + build OK. |
| 2026-06-03 | m0 | STORY-00-03/00-04 | Postgres: pool asyncpg (2–10), Alembic async + migration users (RLS), seed_admin (env, sem segredo), check_postgres. Redis: PriceCache fail-soft + check_redis (agente paralelo). Health agrega postgres+redis. 12 testes (Docker-local) + ruff + mypy. |
| 2026-06-03 | m0 | STORY-00-05 | Auth JWT (ADR-006): bcrypt+JWT HS256, /login /refresh /me, get_current_user, migration refresh_token_hash, gen_hermes_token. Pin bcrypt<5 (incompat passlib). 21 testes + ruff + mypy. |
| 2026-06-03 | m0 | STORY-00-07 | Login: backend seta refresh em cookie httpOnly; front app/(auth)/login (form, loading, erro), access em memória, proxy.ts (Next 16) gating de rota, dashboard placeholder. pnpm lint+build OK; 22 testes backend. |
| 2026-06-03 | m0 | STORY-00-08-09 | [~] CI/CD: .github/workflows/deploy.yml (test→deploy-api→deploy-web), api/fly.toml (release alembic, vm 256, gru). Deploy real + gate de produção PENDENTE de provisionamento cloud manual — ver docs/DEPLOY.md. |
| 2026-06-03 | m0 | — (consolidação) | uv (ADR-010): pyproject = fonte única + uv.lock, removidos requirements*.txt; Dockerfile/CI/pre-commit/docs migrados. Runbook local docker-na-8000 (docs/LOCAL_DEV.md) após liberar a 8000 (processo hermes órfão). Fix login web: NEXT_PUBLIC_API_URL 8001→8000. Refs Next16/uv em project-context/EPIC-00/.claude. Verificado: `uv run` 22 testes/91% + ruff + mypy; Docker /health pg+redis connected, login E2E. |
| 2026-06-03 | m1 | STORY-01-01 | Schema ledger: migration `0003_ledger` (accounts, transactions [+`external_id` c/ índice único parcial p/ dedup Nubank/FITID], fixed_costs, view `monthly_summary`, RLS). Pivô: fonte = extrato Nubank (OFX/CSV) via frontend; gate jun/2026 = 55,48%; alertas compute-on-read (ver plano + memória). 3 testes de schema; suite 25/25; cobertura engines 91% + ruff. Branch `m1-ledger`. |
| 2026-06-03 | m1 | STORY-01-02 | CRUD de contas e categorias. Engine multi-arquivo: `engines/ledger/{accounts,categories,router}.py` (montado no main.py). Migration `0004_categories` (tabela configurável + seed: receitas Flash/Betuel/Salário/Extra, despesas BR, investment/transfer p/ classificação Nubank). DELETE de conta com transações → 409; categoria duplicada → 409; filtro `?kind=`. +11 testes (14 ledger); suite 36/36; cobertura engines 91%; ruff+mypy ok (ledger incluído no mypy do CI). |
| 2026-06-04 | m1 | STORY-01-03 | CRUD de transações (`engines/ledger/transactions.py`): GET paginado c/ filtros `from/to/category/account_id` (envelope items+total), POST/PUT/DELETE. Validação: amount≠0 (422), conta inexistente → 422 (FK), 404 em update/delete inexistente. NUMERIC(15,2) via Decimal(str()). +6 testes; suite 42/42; cobertura engines 92%; ruff+mypy ok. |
| 2026-06-04 | m1 | STORY-01-04/05 | Cashflow (`engines/ledger/cashflow.py`): GET /cashflow (saldo running via window SUM, filtros account/from/to) + GET /cashflow/summary (view monthly_summary; `?month=YYYY-MM` → mês único, 404 sem dados, 422 receita zero). Taxa de poupança validada (10000/-4500 → 55%). +6 testes; suite 48/48; cobertura engines 93%; ruff+mypy ok. Nota: import (01-13-14) NÃO grava investment/transfer como transação p/ a taxa não distorcer. |
| 2026-06-04 | m1 | STORY-01-07 | CRUD custos fixos (`engines/ledger/fixed_costs.py`): GET (filtro `?active=`)/POST/PUT/DELETE em `/api/v1/fixed-costs`. Validação: amount>0, due_day 1-31 (422), 404 em update/delete inexistente. +6 testes; suite 54/54; ruff+mypy ok. |
| 2026-06-04 | m1 | STORY-01-06 | Projeção de caixa (`/cashflow/projection` em cashflow.py): saldo atual + receita recorrente (is_recurring & amount>0) − custos fixos ativos, escalado p/ 30/60/90d; `?account_id` opcional. Fixture autouse `_clean_fixed_costs` blinda a tabela global entre testes. +2 testes; suite 56/56; cobertura engines 94%; ruff+mypy ok. |
| 2026-06-04 | m1 | STORY-01-08 | Alertas compute-on-read. Lógica pura em `engines/ledger/service.py` (today injetado): vencimento ≤5 dias (próxima ocorrência do due_day, clamp fim de mês) + categoria >120% da média dos 3 meses anteriores. Endpoint `GET /cashflow/alerts` (`engines/ledger/alerts.py`). Sem persistir (active_alerts fica p/ m5). +7 testes; suite 63/63; cobertura engines 94.75%; ruff+mypy ok. |
| 2026-06-04 | m1 | STORY-01-09 | Endpoints Hermes (`hermes/router.py`): POST /hermes/expenses e /income. Auth service token scope=hermes (secret próprio; `decode_hermes_token` no security.py) — 401 sem/ inválido, 403 escopo errado, token de usuário rejeitado. amount positivo no request, sinal aplicado pelo endpoint (despesa negativa). conta inexistente → 422. +6 testes; suite 69/69; cobertura engines 94.75%; ruff+mypy ok. |
| 2026-06-04 | m1 | FE-0 (fundação) | Frontend: `types/ledger.ts`, `lib/format.ts` (BRL/%/data/mês pt-BR), `lib/ledger.ts` (hooks React Query: accounts/categories/transactions/summary/projection/alerts + mutation), `components/ui.tsx` (Button/Input/Select/Field/Card), `components/AppShell.tsx` (sidebar + gate de auth). Route group `(app)` com layout; dashboard movido p/ `(app)/dashboard`. Sem deps novas. Verificado: npm lint + build OK. Limitação: reload duro perde token em memória → cai p/ /login (refresh-on-load via cookie é melhoria de auth futura). |
| 2026-06-04 | m1 | STORY-01-10 | Frontend lista de transações `(app)/ledger`: filtros (conta/categoria/intervalo) + paginação (limit 50), tabela com valor colorido gain/loss, estados loading/erro/vazio. Reusa hooks `useTransactions/useAccounts/useCategories`. Verificado: npm lint + build OK (rota /ledger). |
| 2026-06-04 | m1 | STORY-01-11 | Frontend formulário `(app)/ledger/new`: tipo (receita/despesa) + valor positivo (sinal aplicado no envio), conta, data (default hoje), categoria filtrada por kind, descrição, recorrente. Validação client + 422 do backend; sucesso → /ledger via `useCreateTransaction`. Verificado: npm lint + build OK (rota /ledger/new). |
| 2026-06-04 | m1 | STORY-01-12 | Frontend dashboard `(app)/dashboard`: cards de resumo do mês (receita/despesa/saldo/taxa de poupança), projeção 30/60/90 + saldo atual, alertas, e tendência de poupança (barras CSS, sem libs). Reusa `useMonthlySummaries/useProjection/useAlerts`. Verificado: npm lint + build OK (6 rotas). Frontend do m1 completo. |
| 2026-06-04 | m1 | STORY-01-13-14 [~] | Import Nubank: `engines/ledger/importer.py` (parse OFX 1.0.2 SGML + CSV, classificação configurável, dedup por external_id/FITID — investimento/transferência NÃO viram caixa), endpoint `POST /api/v1/ledger/import` (corpo cru, sem python-multipart), `scripts/migrate_ledger.py` (dry-run/--apply), front `(app)/ledger/import`. Setting `ledger_self_identifiers` (PII no .env) p/ transferência interna. +9 testes (unit parsers/classify + endpoint idempotente); suite 78/78; cobertura engines 94.51%; ruff+mypy(22) ok. Validado no extrato real de jan/2026: 63 entradas, income 6/investment 16/expense 41. **Gate jun/2026 PENDENTE do arquivo de junho.** |
| 2026-06-04 | m1 | fix(testes+dados) | Contas fantasma (~30 `Nubank-<hex>`/`acc-<hex>`): causa = testes rodavam no banco real `goodies` e 2 testes de conta não limpavam. Fix de raiz: testes agora rodam em banco dedicado `goodies_test` (conftest força DATABASE_URL + cria/migra o DB on-the-fly), nunca no real; + cleanup nos 2 testes + autouse `_clean_accounts`. Banco real resetado p/ 1 conta 'Nubank' (`fa867c2c…`) e janeiro reimportado (47 tx; 16 investimentos excluídos; dedup idempotente OK). Suíte 78/78 em goodies_test; goodies permaneceu 30→reset (prova de isolamento). |
| 2026-06-04 | m1 | feat(UX transações) | (1) Edição inline de Descrição (clique→input, Enter/blur salva, Esc cancela) e Categoria (select discreto) na `/ledger` via `useUpdateTransaction` (PUT já existente). (2) KPI **Saldo Acumulado** no topo do dashboard (= `projection.current_balance` = SUM(amount)); removida a duplicata "Saldo atual" do card de projeção. (3) `GET /transactions` agora retorna `total_income`/`total_expense` do conjunto filtrado (query agregada sobre o mesmo WHERE) — exibidos em linha discreta na tabela, reativos aos filtros. +1 teste; suite 88/88; cobertura 94%; ruff+mypy ok; npm lint+build ok. |
| 2026-06-04 | m1 | feat(multi-conta + notes) | Migration `0005` (`transactions.notes` + `accounts.account_number` único parcial). CRUD expõe ambos (409 nº duplicado). Importer: `parse_account_number` (ACCTID) + auto-rota (OFX→conta pelo nº; CSV→account_id; 409 conflito); `import_statement` une os nº de conta do DB aos `self_identifiers` → transferência interna Nubank↔Nubank (nº na descrição) vira `transfer` e é excluída (não dupla-conta repasses PJ↔CPF). CLI auto-rota; endpoint conta opcional. Frontend: campo Nota no form + exibição na lista; import com conta auto-detectada. +9 testes; suite 87/87; cobertura engines 94%; ruff+mypy(22) ok. Dados reais: 2 contas (Nubank_CPF `4288917-8`, Nubank_CNPJ `58022571-6`), reimport jan–jun (CPF 226 tx, CNPJ 17). Externos (Santander `1095178-6`) fora da dedup por ora (decisão do usuário) — afeta a taxa de poupança até serem listados. |
| 2026-06-04 | m1 | STORY-01-15 | Tab **Análise** (`/analise-ledger`). Backend: novo `GET /api/v1/cashflow/by-category?month=YYYY-MM` (opcional→acumulado) — agrega `transactions` por categoria+lado com `SUM(ABS)` + `%` por seção via window `OVER (PARTITION BY side)` (NULLIF evita /0); vazio → 200 (não 404). Frontend: hooks `useCategoryBreakdown` + CRUD de categorias (`useCreate/Update/DeleteCategory`) e custos fixos (`useCreate/Update/DeleteFixedCost`); página única com 3 cards — breakdown receitas/gastos (barras CSS, seletor de mês + "Tudo"), gestão de categorias inline (nome/kind/ativa/excluir, add), custos recorrentes CRUD inline (nome/valor/dia/categoria + total mensal); NAV. Caveat na UI: investimentos/transferências internas não entram no caixa (não batem com a planilha onde "INVESTIMENTOS" é ~55% dos gastos — alocação é m2). +4 testes; suite 92/92; cobertura engines 94% (cashflow.py 100%); ruff+mypy(22) ok; npm lint+build ok. |
| 2026-06-04 | m1 | refator(ledger kind-aware) | **Conserto da modelagem** (saldo fantasma + taxa distorcida): o import deixa de PULAR investimento/transferência e passa a **gravar tudo** com coluna `kind`. Migration `0006` (`transactions.kind` CHECK+índice, backfill por sinal/categoria; `categories.match_patterns text[]` + seed dos 6 destinos; **DROP/CREATE view `monthly_summary` kind-aware**: `total_expense`=só consumo, `savings_rate`=(receita−consumo)/receita **(B)**, +`total_invested`+`investment_rate` **(A)**; `net_cashflow`=receita−consumo, ≠ saldo). Classificação **configurável** via `categories.match_patterns` (substitui `_INVESTMENT_KW`): `importer.classify(entry, rules, self_ids)` por substring (maior pattern vence); `_load_rules`. Endpoints kind-aware: transactions (+`kind`, deriva da categoria, agg `total_invested`), cashflow (`/summary`+A, `/by-category` 3 seções por kind), categories (CRUD `match_patterns`), hermes (insere `kind`). Frontend: tipos +kind/A; dashboard cards Investido+Taxa de investimento; Análise 3ª seção Investimentos + edição de patterns; lista colore por kind (investimento ≠ vermelho); form ganha 3º tipo Investimento. **Decisões travadas**: poupança canônica=(B) p/ o gate, (A) como KPI bônus; achados OFX: Flash mão-dupla (`securitizadora`=income vs `flash capital`=invest; "debênture" não existe no memo), "Resgate RDB" positivo=investment, Toro/Santander mesmo CNPJ (pattern `corretora de titulos`). +9 testes (suite 97/97); cobertura engines 94% (cashflow 100%); ruff+mypy(22) ok; npm lint+build ok. Reset+reimport jan–jun (320 tx): mecanismo validado (jan: 5 destinos, saldo real, corretora fora do consumo). **Gate aberto** até `.env LEDGER_SELF_IDENTIFIERS` + junho completo (ver nota do Gate m1). |
| 2026-06-04 | m1 | infra(.env raiz + reset) | `config.py` agora lê o `.env` do **raiz** do repo por caminho absoluto (`_ROOT_ENV`) — antes lia relativo a `api/` e ignorava o `.env` que o usuário pôs no raiz (alinhado ao `.env.example` raiz). Novo `scripts/reset_ledger.py --yes` (apaga + reimporta todos os OFX de `files/nubank/`, com banner do alvo + resumo B/A). `.env.example`: doc do formato de `LEDGER_SELF_IDENTIFIERS` (substring case-insensitive; nº de conta já automático). `LEDGER_SELF_IDENTIFIERS` setado (3 itens: nome 22 matches, CNPJ 9, CPF 1=mascarado). Reset rodado: transferências internas detectadas sobem (jan 1→4), mas savings_rate ainda 3–34%/mês — causa = receita subcontada (Santander fora) + junho parcial, NÃO o engine. `DATABASE_URL` do `.env` usa host `postgres` (docker); scripts no host precisam de override `localhost`. Suite 99/99; ruff+mypy(23) ok. |
| 2026-06-04 | m2 | STORY-02-01 | Migration `0007_portfolio`: `asset_operations` (id, user_id, broker, asset_symbol, asset_category, tipo CHECK, quantidade>0, valor_unitario>=0, data_operacao, notes, external_id, created_at); `portfolio_targets` (id, user_id, category, target_pct 0<x<=100, UNIQUE user_id+category, created_at). Índices: user_id (RLS), user_id+asset_symbol (XIRR per-asset), data_operacao, external_id UNIQUE PARTIAL. RLS habilitado ambas. Testes (6): exists, columns, tipo/quantidade constraints, unique category. Scaffold `api/engines/portfolio/__init__.py`. Suite 105/105 verde; ruff/mypy ok. Bridge m1↔m2 pronta para seed (02-02). |
| 2026-06-04 | m2 | **B1: STORY-02-02 + STORY-02-05** | **STORY-02-02 (seed portfolio_targets):** `engines/portfolio/targets.py` (PORTFOLIO_TARGETS const, seed_targets + get_targets async funcs); `scripts/seed_portfolio_targets.py` (idempotent CLI); 6 targets (Ações 10%, Aposentadoria 12.5%, Cripto 5%, ETFs 12.5%, FIIs 10%, Renda Fixa 50%); ON CONFLICT upsert. Tests: create, idempotent, sum=100%, empty list (suite 5/5). **STORY-02-05 (XIRR — gate crítico):** `engines/portfolio/xirr.py` — scipy.optimize.brentq implementation, exact CLAUDE.md formula (NPV solver for annualized rate). Edge cases: <2 flows→nan, non-convergent→nan, auto-ordering, DCA scenarios. Tests: 13 cases (1-year, Tesouro IPCA, cripto volatile, loss, zero net, high gain, precision) vs Excel reference (±0.1pp tolerance). +18 testes portfolio; **suite 123/123 verde**, portfolio coverage 100%, global 95%; ruff+mypy strict. Commit f71bfc2. |
| 2026-06-04 | m2 | **STORY-02-03** | **CRUD de operações com validação de tipos:** `engines/portfolio/operations.py` — 6 async funcs (create, get, list, update, delete); validação tipo CHECK {compra, venda, dividendo, juros, aporte, resgate}, quantidade>0, valor_unitario>=0, external_id UNIQUE PARTIAL. `engines/portfolio/router.py` — 5 endpoints (POST 201, GET list+filters, GET {id} 404, PUT 200/404, DELETE 204/404); Pydantic @field_validator tipo; asyncpg error handling CheckViolation→422, UniqueViolation→422. `tests/portfolio/test_operations.py` — 16 testes TDD (create valid, invalid tipo/qty/price, list filters, CRUD lifecycle, 404s); `tests/portfolio/conftest.py` — fixtures api + auth_headers + cleanup (DELETE FROM asset_operations before user). +16 testes; **suite 139/139 verde**, portfolio 93%/84%, global 94%; ruff (E501 quebrada, B008 noqa FastAPI)+mypy strict. Commit 67cf200. Bridge pronta para 02-04 (DCA). |
| 2026-06-04 | m2 | **STORY-02-04** | **DCA: Cálculo de preço médio ponderado:** `engines/portfolio/operations.py` — 2 async funcs (calculate_dca_by_asset + calculate_dca_all); formula SUM(qty × price) / SUM(qty) where tipo IN ('compra','aporte'), exclui venda/resgate/dividendo/juros (rendimentos). `engines/portfolio/router.py` — 2 GET endpoints (/dca todos ativos, /dca/{asset_symbol} um ativo); rota /dca **antes** de /{operation_id} (evita colisão FastAPI path). `tests/portfolio/test_dca.py` — 10 testes TDD (single compra, múltiplas compras weighted avg, ignore venda/dividendo/juros, aporte incluído, ignore resgate, 404 not found, all list, all empty). +10 testes; **suite 149/149 verde**, portfolio 93%, global 92%+; ruff+mypy strict. Commit 1893c7f. B1-B2 cascade: 02-02/02-05/02-03/02-04 completos; próximo B3 inicia 02-06 (XIRR endpoints). |
| 2026-06-05 | m2 | **Gate 02-17-18 FECHADO — reconciliação vs planilha** | Vitor enviou a planilha DESEMPENHO CARTEIRA (valor atual por ativo). Reconciliação: **custo total bate 99,95%** (meu R$22.440,64 vs R$22.451,21); **quantidades exatas** (NASD11 29=29). Divergências de custo pequenas e explicadas: NASD11 +R$39,64 = sistema MAIS preciso (preço real B3 vs médio defasado da planilha, confirmado pelo Vitor); Tesouro ~−R$41 = fracionários/cobertura Movimentação. Preços atuais alinhados aos da planilha e persistidos no banco local. **XIRR CONSOLIDADO = 15,25% a.a.** (B3+Tesouro+Flash; Guanabara R$258 fora — sem data de aporte; cripto m4). Gate validado por reconciliação (a planilha não tem XIRR único). **m2 = 17/17.** |
| 2026-06-05 | m2 | **Gate 02-17-18 — debêntures Flash (RF pré) + XIRR consolidado** | Fonte RF real: `files/debentures-flash/integralizacoes.json` (12 aportes R$1.000, pré 24% a.a. = fator mensal 1,78%; gitignored). `engines/portfolio/rf_pre.py` (valor_atual_pre, 4 testes); `scripts/seed_debentures_flash.py`. Decisão: **dev usa Postgres LOCAL** (`goodies@localhost`); Supabase só no deploy. Pipeline completo rodado no banco local (`demo@goodies.local`): seed targets (6) + import B3 (288 ops + 20 preços) + Flash (12 aportes). **XIRR CONSOLIDADO = 16,53% a.a.** (B3+Tesouro+Flash); patrimônio R$24.212,17. Por categoria: **Renda Fixa 23,94% (≈ pré 24% — valida a fórmula Flash)**, FIIs 19,60%, ETFs 17,05%, Aposentadoria 8,91%, Ações 2,75%. Pendente p/ fechar ±0,1pp: `=XIRR` do Excel na mesma base (B3+TD+Flash). Cripto = m4; Guanabara CDB (R$200) + Caixinha = menores, opcionais. Suite 218/218. Commit (Flash). |
| 2026-06-04 | m2 | **Gate 02-17-18 — fonte real B3/Toro + Tesouro Direto** | Dados reais chegaram (relatórios B3 XLSX em `files/b3/`, gitignored): Movimentação completa 2024/2025/2026 + consolidados. `engines/portfolio/b3_import.py` (parser Movimentação + preços de posição, 16 testes); `scripts/import_b3.py` (CLI, dry-run/--commit/--snapshot). **Descoberta:** Movimentação cobre só Toro/B3 + Tesouro (NU) — **não** cobre RF (Flash/Guanabara) nem cripto (virão de wallet scan/Binance no m4). Futuros de mini-índice (WIN, qty=0) corretamente excluídos. **Resultado do gate (subset B3+TD, 288 ops set/24→mai/26):** comprado R\$ 10.626,83, valor atual R\$ 10.929,26, **XIRR Python = 10,85% a.a.** (Tesouro R\$ 3.215,11 = posicao.json, validação cruzada). **Pendências do gate:** (1) persistir no banco de produção — `import_b3 --commit` precisa rodar no ambiente do Vitor (Supabase inacessível do sandbox); (2) comparar com `=XIRR` do Excel na mesma base B3+TD p/ fechar ±0,1 pp. Commit 10f797a. |
| 2026-06-04 | m2 | **Fase C — frontend 02-13→02-16 + código do gate 02-17-18** | **Frontend do Portfolio (Next.js 16 + Recharts 3.8.1).** `web/types/portfolio.ts`, `web/lib/portfolio.ts` (hooks React Query: usePositions/useAllocation/useXIRR/useRebalancing/useAssetOperations/useSetManualPrice), `web/lib/format.ts` (formatRate, formatPP). Páginas em `app/(app)/portfolio/`: **02-13** posições (preço atual editável inline, badge stale), **02-14** histórico + filtros, **02-15** alocação (pizza Recharts + barras atual vs meta + desvio), **02-16** rebalanceamento (aporte→sugestões), + visão geral (XIRR headline). Nav no AppShell. `pnpm lint` limpo, `pnpm build` OK (15 rotas). Commit 2bba8e1. **Código do gate 02-17-18 pronto e testado** (`engines/portfolio/migration.py` + `scripts/migrate_portfolio.py`, 8 testes); falta rodar com CSV real + XIRR Excel (precisa de input do Vitor). |
| 2026-06-04 | m2 | **Fase A — backend 02-06→02-12** | **Batch de 7 stories de cálculo do Portfolio Engine.** Migração `0008_asset_prices` (preço manual p/ valoração m2, upsert por ticker; compatível c/ Market Engine m3). Novo `engines/portfolio/service.py` (orquestração + funções puras) e `analytics_router.py` (prefix `/api/v1/portfolio`). **02-06** XIRR por ativo/categoria/consolidado (cashflows ADR-002, posição atual = qtd_net × preço; cache Redis `xirr:consolidated:{user_id}` TTL 1h + invalidação ADR-008). **02-07** posições valoradas (qtd_net, DCA, custo, valor atual, resultado, stale ADR-004) + `scripts/seed_asset_prices.py` (10 preços do posicao.json). **02-08** alocação atual vs meta + desvio_pp (fixture `portfolio_user` com targets). **02-09** rebalanceamento (`suggest_rebalancing` Arquitetura §7, nunca vende). **02-10** rendimentos dividendo/juros separados do capital (filtro período). **02-11** IR RV (Ações/ETF 0.15, FIIs 0.20; prejuízo→0). **02-12** IR cripto mensal (isenção 35k, alerta 28k=80%, ganho via DCA). +33 testes (test_xirr_endpoint, test_positions, test_allocation, test_rebalancing, test_income, test_ir_estimate, test_ir_crypto); **suite 190/190 verde**, portfolio cov 97%; ruff+mypy strict. Commits b8c8c0e→e4a1c59. **Próximo: Fase B (gate 02-17-18) — precisa do CSV real da aba OPERAÇÕES + XIRR do Excel.** |
