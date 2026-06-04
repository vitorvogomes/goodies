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
| 01-13-14 | Migração + validação extrato Nubank (OFX/CSV) | [~] | — |

**Gate m1:** taxa de poupança junho/2026 == 55,48% (±0,1pp). PENDENTE: subir o export Nubank de jun/2026 em `files/nubank/`, importar e validar. Backend+frontend de import prontos e validados com janeiro (63 entradas; income 6 / investment 16 / expense 41).

---

## Milestone m2 — Portfolio Engine

| # | Story | Status | Commit |
|---|---|---|---|
| 02-01 | Schema de banco (asset_operations, portfolio_targets, positions view) | [ ] | — |
| 02-02 | Seed portfolio_targets (alvos do Vitor) | [ ] | — |
| 02-03 | CRUD de operações com validação de tipos | [ ] | — |
| 02-04 | Cálculo de preço médio ponderado (DCA) | [ ] | — |
| 02-05 | **XIRR — implementação e testes (gate crítico)** | [ ] | — |
| 02-06 | Endpoint XIRR por ativo e consolidado | [ ] | — |
| 02-07 | Posição atual por ativo (valor com preço manual) | [ ] | — |
| 02-08 | Cálculo de alocação atual vs. meta + desvio | [ ] | — |
| 02-09 | Motor de rebalanceamento | [ ] | — |
| 02-10 | Rastreamento de rendimentos separado (FII, JCP) | [ ] | — |
| 02-11 | Estimativa de IR por categoria | [ ] | — |
| 02-12 | IR cripto: consolidação mensal + alerta 80% | [ ] | — |
| 02-13 | Frontend — tabela de posições | [ ] | — |
| 02-14 | Frontend — histórico de operações | [ ] | — |
| 02-15 | Frontend — alocação vs. meta (pizza chart) | [ ] | — |
| 02-16 | Frontend — tela de rebalanceamento | [ ] | — |
| 02-17-18 | **Migração + validação XIRR (gate crítico)** | [ ] | — |

**Gate m2:** XIRR Python == Excel XIRR nos dados históricos (±0,1 pp).

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
