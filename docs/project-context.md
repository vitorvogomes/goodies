# Goodies — Project Context

> Este arquivo é injetado automaticamente pelo GSD-Pi no início de cada sessão de implementação no Claude Code.
> Última atualização: 2026-06-02 (Minerva)

---

## O que é o Goodies

Plataforma pessoal de controle financeiro para substituir uma planilha Google Sheets com 22 meses de histórico. Usuário único: Vitor. O critério de done é simples: **Vitor toma decisões financeiras com dados corretos, sem abrir a planilha.**

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI 0.111+ / Python 3.12 |
| Frontend | Next.js 14 (App Router) / TypeScript |
| Database | Supabase (Postgres 15) |
| Cache | Redis via Upstash |
| Backend deploy | Fly.io Hobby |
| Frontend deploy | Vercel Hobby |
| Scheduler | APScheduler (no mesmo processo FastAPI) |

---

## Estrutura do projeto

```
goodies/
├── api/
│   ├── main.py                    # FastAPI app, routers, CORS
│   ├── config.py                  # pydantic-settings, env vars
│   ├── auth/                      # JWT (login, refresh, middleware)
│   ├── engines/
│   │   ├── ledger/                # transações, contas, taxa de poupança
│   │   ├── portfolio/             # operações, XIRR, rebalanceamento
│   │   ├── market/                # preços, cache, fetchers de API
│   │   └── analytics/             # benchmarks, projeções, alertas
│   ├── workers/                   # APScheduler jobs (preços, wallets, alertas)
│   ├── hermes/                    # endpoints para o agente Discord
│   └── db/                        # asyncpg pool, migrations (Alembic)
├── web/
│   ├── app/                       # Next.js App Router
│   ├── components/                # Recharts, tabelas, alertas
│   └── lib/                       # cliente HTTP, auth utils
└── docs/
    ├── 05_Epicos/                  # épicos do projeto
    └── 06_Stories/                 # user stories com critérios de aceite
```

---

## 4 Engines e suas responsabilidades

**Ledger Engine** — controle de caixa
- Transações (receitas/despesas), contas, categorias, custos fixos
- Taxa de poupança = `(receita − despesa) / receita × 100`
- Projeção de caixa 30/60/90 dias

**Portfolio Engine** — investimentos
- Operações de compra/venda/rendimento com timestamp (base para XIRR)
- **XIRR** (Extended IRR) via `scipy.optimize.brentq` — métrica principal de retorno
- Motor de rebalanceamento: distribui aporte proporcional aos desvios negativos
- Estimativa de IR por categoria

**Market Engine** — preços automáticos
- B3: BRAPI.dev (ações, ETFs, FIIs) — TTL 4h
- Cripto: CoinGecko (BTC, ETH, SOL, PENDLE, HYPE, USDT) — TTL 2h
- Tesouro Direto: API pública com matching flexível por nome de título
- Wallet scan: Etherscan (ETH/ARB/HYPE), Solscan (SOL), Liquid Network (L-BTC), Binance API
- Fallback: Redis → Postgres (`asset_prices`) → manual — nunca bloqueia

**Analytics Engine** — análise e metas
- XIRR vs benchmarks (CDI/IPCA/IBOV no mesmo período)
- Retorno real = `(1 + nominal) / (1 + inflação) − 1`
- Projeções em 3 cenários (6%, 10%, 14% a.a.)
- Metas: Reserva (R$ 50.872) e LF (R$ 1.271.802)
- Sistema de alertas proativos

---

## Decisões arquiteturais críticas (não mudar sem criar ADR em 07_Decisoes.md)

1. **XIRR em Python** (scipy) — não em SQL. Cacheado no Redis (TTL 1h), invalidado ao inserir operação.
2. **APScheduler no mesmo processo FastAPI** — não Celery. Workers são idempotentes.
3. **Dados manuais são fallback, nunca bloqueantes.** `asset_prices.is_manual = true` para ativos sem API.
4. **Liquid Network tem client dedicado** (`fetchers/wallets/liquid.py`) — não reutilizar fetcher Bitcoin mainchain. Base URL: `blockstream.info/liquid/api/`.
5. **Hermes é opcional** — Goodies funciona 100% sem ele. Endpoints `/hermes/*` têm service token separado.
6. **JWT custom no FastAPI** — Supabase Auth não é usado para autenticação de usuário (apenas para conexão de banco).
7. **Refresh token em httpOnly cookie** — access token em memória (não localStorage).

---

## Regras de XIRR (implementação correta)

Sinal dos cashflows:
- **Compra** → valor **negativo** (saída de caixa)
- **Venda / rendimento** → valor **positivo** (entrada)
- **Posição atual** → valor **positivo** na data de hoje (valor de mercado atual)

O XIRR de cripto atualmente deve ser negativo (~-18% a.a.) — isso é esperado e correto.

---

## Convenções de código

- **Linting:** `ruff` (backend), `eslint` (frontend) — configurados em `pre-commit`
- **Type checking:** `mypy --strict` no backend
- **Testes:** `pytest` com `pytest-asyncio` para endpoints async
- **Cobertura mínima:** 80% para engines críticas (Portfolio e Analytics)
- **Logs:** `structlog` em JSON em produção, colorido em dev
- **Erros de API externa:** logar, retornar dado cacheado + `"stale": true`. Nunca retornar 5xx por falha de provider externo.
- **Migrations:** Alembic. Rodar `alembic upgrade head` antes de qualquer deploy.

---

## Gates de qualidade por milestone

| Milestone | Gate |
|---|---|
| m0-foundation | `GET /api/v1/health` retorna 200 com Postgres + Redis. Login funciona. Deploy automático funcionando. |
| m1-ledger | Taxa de poupança de junho/2026 bate com planilha (±0,1%). |
| m2-portfolio | XIRR Python bate com Excel XIRR nos dados históricos (±0,1 pp). |
| m3-market-data | Preços B3 e cripto atualizando automaticamente. Sem erro em 48h de operação. |
| m4-broker-integration | Posições cripto escaneadas automaticamente. Saldo bate com wallets reais (validação manual). |
| m5-analytics | CDI/IPCA/IBOV no dashboard. Alertas ativos (pelo menos concentração Flash visível). |
| m6-observability | Falha de worker notifica no Discord < 5min. |
| m7-frontend | 30 dias de uso sem abrir a planilha. |

---

## Variáveis de ambiente necessárias (ver .env.example)

```
DATABASE_URL, UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN,
JWT_SECRET_KEY, JWT_ALGORITHM, HERMES_SERVICE_TOKEN,
BRAPI_TOKEN, BINANCE_API_KEY, BINANCE_SECRET_KEY,
ETHERSCAN_API_KEY, SENTRY_DSN, ENVIRONMENT, CORS_ORIGINS
```

---

## Wallets e endereços configurados

| Wallet | Rede | Endereço |
|---|---|---|
| ETH/ARB/HYPE | Ethereum/Arbitrum/HyperEVM | `${WALLET_EVM_ADDRESS}` |
| SOL | Solana | `${WALLET_SOL_ADDRESS}` |
| Liquid (L-BTC) | Liquid Network | `${WALLET_LIQUID_ADDRESS}` |
| Binance | — | via API key (spot + earn) |

---

## Skills recomendadas (instalar no repo via Claude Code)

```bash
# Core — instalar antes do m0
npx skills add supabase/agent-skills/supabase-postgres-best-practices
npx skills add mattpocock/skills/tdd
npx skills add vercel-labs/next-skills/next-best-practices

# Frontend — instalar antes do EPIC-07
npx skills add anthropics/skills/frontend-design
npx skills add leonxlnx/taste-skill/high-end-visual-design
```

Fonte: skills.sh — compatíveis com Claude Code.

---

## O que NÃO fazer

- ❌ Calcular retorno como `(resultado - aplicado) / aplicado` — isso é metodologicamente errado para DCA
- ❌ Reutilizar fetcher de Bitcoin mainchain para Liquid Network
- ❌ Chamar Binance API on-demand — usar apenas via cron
- ❌ Armazenar access_token em localStorage
- ❌ Retornar HTTP 500 porque uma API externa está fora — logar, usar cache, retornar `stale: true`
- ❌ Criar dependência do Goodies no Hermes — o Goodies é autônomo
- ❌ Usar Celery para workers — APScheduler no processo é suficiente
- ❌ Commitar secrets ou `.env` com valores reais

---

## Links dos documentos do vault (referência)

Os documentos de planejamento estão em `C:\Users\Vitor\OneDrive\Documents\Vault_Vitor\04_Projetos\Goodies\`:
- `01_PRD.md` — requisitos completos
- `02_Arquitetura.md` — design técnico detalhado
- `03_Stack.md` — stack com versões e configs
- `04_UX.md` — design system, layouts de tela, copy financeiro (Sally + Aspásia)
- `07_Decisoes.md` — ADRs (8 decisões arquiteturais)
- `05_Epicos/` — 8 épicos (EPIC-00 a EPIC-07)
- `06_Stories/` — user stories com critérios de aceite
