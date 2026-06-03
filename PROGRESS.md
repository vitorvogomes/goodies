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
| 00-07 | Tela de login no frontend | [x] | — |
| 00-08-09 | GitHub Actions + Deploy Fly.io e Vercel | [ ] | — |

**Gate m0:** `GET /api/v1/health` → 200 com Postgres + Redis. Login funciona.

---

## Milestone m1 — Ledger Engine

| # | Story | Status | Commit |
|---|---|---|---|
| 01-01 | Schema de banco (accounts, transactions, fixed_costs, monthly_summary view) | [ ] | — |
| 01-02 | CRUD de contas e categorias | [ ] | — |
| 01-03 | CRUD de transações com validação | [ ] | — |
| 01-04 | Cálculo de saldo running e resumo mensal | [ ] | — |
| 01-05 | Cálculo de taxa de poupança | [ ] | — |
| 01-06 | Projeção de caixa 30/60/90 dias | [ ] | — |
| 01-07 | CRUD de custos fixos | [ ] | — |
| 01-08 | Alertas de vencimento e categoria acima de 120% | [ ] | — |
| 01-09 | Endpoints Hermes (POST /expenses, POST /income) | [ ] | — |
| 01-10 | Frontend — lista de transações + filtros | [ ] | — |
| 01-11 | Frontend — formulário de nova transação | [ ] | — |
| 01-12 | Frontend — dashboard de caixa | [ ] | — |
| 01-13-14 | Migração + validação CSV (FLUXO DE CAIXA) | [ ] | — |

**Gate m1:** taxa de poupança junho/2026 bate com planilha (±0,1%).

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
