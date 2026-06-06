---
tipo: arquitetura
projeto: Goodies
versao: "1.0"
autor: BMAD/Winston (Architect) via Minerva
data: 2026-06-02
status: aprovado
tags: [goodies, arquitetura, design, tecnico]
---

# Goodies — Arquitetura Técnica

> Produzido por Winston (Architect/BMAD) com base no PRD (`01_PRD.md`) e no contexto financeiro (`08_Contexto_Financeiro.md`).
> Este documento é a referência técnica para implementação. Decisões formais estão em `07_Decisoes.md`.

---

## 1. Visão geral do sistema

Goodies é uma aplicação web monousuário com backend em Python e frontend em Next.js. A arquitetura segue um padrão de **4 engines independentes** com dados compartilhados via banco de dados central (Supabase/Postgres), cache de preços em Redis e workers assíncronos para coleta de dados externos.

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENTE                              │
│  Next.js (Vercel) ─── API Routes ─── FastAPI (Fly.io)      │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │         CORE BACKEND           │
              │  ┌──────────┐ ┌─────────────┐ │
              │  │  Ledger  │ │  Portfolio  │ │
              │  │  Engine  │ │   Engine    │ │
              │  └──────────┘ └─────────────┘ │
              │  ┌──────────┐ ┌─────────────┐ │
              │  │  Market  │ │  Analytics  │ │
              │  │  Engine  │ │   Engine    │ │
              │  └──────────┘ └─────────────┘ │
              └───────────────┬───────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   Supabase             Redis (Upstash)        External APIs
  (Postgres)           (price cache)          (BRAPI, CoinGecko,
  (Auth/JWT)                                   Binance, BCB, etc.)
        │
   Hermes (Discord) ──── REST API do Goodies
```

---

## 2. Componentes

### 2.1 FastAPI Backend (`/api`)

**Responsabilidade:** lógica de negócio, cálculos financeiros, orquestração de engines.

**Estrutura de pacotes:**
```
api/
├── main.py                    # app FastAPI, routers, CORS, middleware
├── config.py                  # settings (pydantic-settings, env vars)
├── auth/
│   ├── jwt.py                 # criação e validação de JWT
│   └── dependencies.py        # FastAPI dependency injection (get_current_user)
├── engines/
│   ├── ledger/
│   │   ├── router.py          # /ledger/* endpoints
│   │   ├── service.py         # lógica de negócio (taxa de poupança, projeção)
│   │   ├── models.py          # Pydantic schemas (request/response)
│   │   └── queries.py         # queries SQL (via asyncpg direto ou SQLAlchemy)
│   ├── portfolio/
│   │   ├── router.py          # /portfolio/* endpoints
│   │   ├── service.py         # XIRR, preço médio, rebalanceamento, IR
│   │   ├── xirr.py            # implementação isolada do XIRR (testável)
│   │   ├── models.py
│   │   └── queries.py
│   ├── market/
│   │   ├── router.py          # /market/* endpoints (leitura de preços)
│   │   ├── service.py         # orquestração de price fetchers
│   │   ├── cache.py           # interface Redis (get/set com TTL)
│   │   ├── fetchers/
│   │   │   ├── brapi.py       # B3 prices
│   │   │   ├── coingecko.py   # cripto prices
│   │   │   ├── binance.py     # Binance API
│   │   │   ├── bcb.py         # BCB (CDI, IPCA)
│   │   │   ├── treasury.py    # Tesouro Direto
│   │   │   ├── wallets/
│   │   │   │   ├── etherscan.py    # ETH/ARB/HYPE
│   │   │   │   ├── solscan.py      # SOL
│   │   │   │   ├── liquid.py       # Liquid Network (L-BTC)
│   │   │   │   └── hyperliquid.py  # HYPE on-chain
│   │   │   └── base.py        # interface abstrata de fetcher (ABC)
│   │   └── models.py
│   └── analytics/
│       ├── router.py          # /analytics/* endpoints
│       ├── service.py         # benchmarks, projeções, alertas
│       ├── calculations.py    # fórmulas financeiras isoladas (testáveis)
│       └── models.py
├── workers/
│   ├── price_worker.py        # scheduler APScheduler: atualiza cache Redis
│   └── alert_worker.py        # avalia alertas periodicamente
├── hermes/
│   └── router.py              # /resumo-geral, /alertas, /portfolio/xirr (endpoints Hermes)
└── db/
    ├── connection.py          # pool asyncpg + Supabase connection string
    └── migrations/            # SQL de migrations (Alembic ou sqitch)
```

**Padrão de erro:** erros de API externa nunca propagam como 5xx para o cliente — logar, retornar último valor cacheado + campo `stale: true`.

### 2.2 Next.js Frontend (`/web`)

**Responsabilidade:** interface de usuário, visualizações, formulários de entrada.

**Estrutura de páginas:**
```
web/
├── app/
│   ├── (auth)/
│   │   └── login/page.tsx           # tela de login (JWT)
│   ├── dashboard/page.tsx            # visão geral: patrimônio, XIRR, alertas
│   ├── ledger/
│   │   ├── page.tsx                  # lista de transações + filtros
│   │   └── new/page.tsx              # formulário de nova transação
│   ├── portfolio/
│   │   ├── page.tsx                  # posições, alocação, rebalanceamento
│   │   └── operations/page.tsx       # histórico de operações
│   ├── market/page.tsx               # preços atuais, wallets
│   └── analytics/page.tsx            # XIRR, benchmarks, projeções, metas
├── components/
│   ├── charts/                       # Recharts components
│   ├── tables/                       # tabelas de dados
│   ├── alerts/                       # card de alertas ativos
│   └── ui/                           # shadcn/ui ou Radix primitives
├── lib/
│   ├── api.ts                        # cliente HTTP para o FastAPI
│   └── auth.ts                       # gestão de JWT no cliente
└── types/                            # tipos TypeScript espelhando os modelos do backend
```

**Estado:** React Query (TanStack Query) para cache de server state — sem Redux. Revalidação automática dos dados com `staleTime` ajustado por engine (analytics: 5min, market: 2min).

### 2.3 Workers de Coleta

**APScheduler** integrado ao FastAPI (não Celery — sem complexidade de broker para uso monousuário):

| Worker | Schedule | O que faz |
|---|---|---|
| `price_b3` | Cron: dias úteis 9h–18h, a cada 4h | Fetcha BRAPI → salva Redis |
| `price_crypto` | Cron: todo dia, a cada 2h | Fetcha CoinGecko + Binance → salva Redis |
| `wallet_scan` | Cron: todo dia 8h, 14h, 20h | Etherscan + Solscan + Liquid → salva `wallet_positions` |
| `benchmark_daily` | Cron: todo dia 22h | BCB (CDI/IPCA) + yfinance (IBOV) → salva `benchmark_data` |
| `alert_eval` | Cron: todo dia 8h | Avalia todos os alertas, salva `active_alerts` |

---

## 3. Modelo de dados

### 3.1 Diagrama ER resumido

```
accounts ──< transactions
accounts ──< fixed_costs

asset_operations >── asset_prices (via ticker lookup)
asset_operations ──> positions (view)
portfolio_targets (alocação meta por categoria)

wallet_positions (snapshot on-chain + Binance)
asset_prices (último preço por ticker, cache persistido)

goals (Reserva, LF — fórmulas e progress)
benchmark_data (CDI, IPCA, IBOV por data)
active_alerts (alertas em aberto)
```

### 3.2 Tabelas principais

#### `accounts`
```sql
CREATE TABLE accounts (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL,           -- ex: "Nubank", "Binance", "Flash"
  type         TEXT NOT NULL,           -- "bank", "broker", "crypto", "manual"
  currency     TEXT NOT NULL DEFAULT 'BRL',
  created_at   TIMESTAMPTZ DEFAULT now()
);
```

#### `transactions`
```sql
CREATE TABLE transactions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id   UUID NOT NULL REFERENCES accounts(id),
  date         DATE NOT NULL,
  amount       NUMERIC(15,2) NOT NULL,  -- positivo = receita, negativo = despesa
  category     TEXT NOT NULL,
  description  TEXT,
  is_recurring BOOLEAN DEFAULT false,
  created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_category ON transactions(category);
```

#### `fixed_costs`
```sql
CREATE TABLE fixed_costs (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL,
  amount       NUMERIC(15,2) NOT NULL,
  due_day      INTEGER NOT NULL,        -- dia do mês (1–31)
  category     TEXT NOT NULL,
  is_active    BOOLEAN DEFAULT true,
  created_at   TIMESTAMPTZ DEFAULT now()
);
```

#### `asset_operations`

> ⚠️ **Reconciliação com a implementação real (m2 / §3.5 do débito).** O schema abaixo é o
> *projeto* original; a migração **`0007_portfolio`** divergiu e é a fonte de verdade:
> - Colunas reais: **`asset_symbol`** (não `ticker`), **`asset_category`** (não `category`,
>   e os valores são as 6 categorias canônicas de `engines/portfolio/constants.py`:
>   "Ações Nacionais", "ETFs", "FIIs", "Renda Fixa", "Aposentadoria", "Cripto"), **`tipo`**
>   (não `op_type`, com CHECK `compra|venda|dividendo|juros|aporte|resgate`),
>   `quantidade` (NOT NULL, CHECK > 0), `valor_unitario` (NOT NULL, CHECK >= 0),
>   `data_operacao`, `external_id` (dedup), `user_id` (RLS). **Não existe `total_amount`** — o
>   valor é `quantidade * valor_unitario`, com o sinal do cashflow derivado de `tipo`
>   (`service.signed_amount`).
> - **Não existem `models.py` nem `queries.py`** no `engines/portfolio/` — as queries são SQL
>   inline em `service.py`/`operations.py` (asyncpg direto, ADR sem ORM) e as respostas dos
>   endpoints ainda são `dict[str, Any]` (contrato Pydantic tipado nasce no Market Engine m3).
> - **Não existe a VIEW `positions`** — posições, alocação e XIRR são calculados em Python
>   (`service.calculate_positions` / `calculate_allocation` / `calculate_portfolio_xirr`).
> - `asset_prices` é **global** (PK `ticker`, sem `user_id`); ver a seção `asset_prices`.

```sql
CREATE TABLE asset_operations (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker       TEXT NOT NULL,           -- ex: "PETR4", "BTC", "HFOF11"
  category     TEXT NOT NULL,           -- "acoes", "etf", "fii", "rf", "cripto", "aposentadoria"
  date         DATE NOT NULL,
  op_type      TEXT NOT NULL,           -- "buy", "sell", "income" (rendimento)
  quantity     NUMERIC(20,8),           -- null para renda fixa por valor
  unit_price   NUMERIC(20,8),
  total_amount NUMERIC(15,2) NOT NULL,  -- pode diferir de qtd*preço por taxas
  broker       TEXT,
  notes        TEXT,
  created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_asset_ops_ticker ON asset_operations(ticker);
CREATE INDEX idx_asset_ops_date ON asset_operations(date);
CREATE INDEX idx_asset_ops_category ON asset_operations(category);
```

**Nota XIRR:** o cálculo de XIRR usa `(data_operacao, sinal)` de cada operação (ver caixa acima:
não há `total_amount`). Compras/aportes: saída de caixa (negativo). Vendas/resgates/rendimentos:
entrada (positivo). Posição atual: entrada na **data de avaliação** (`service.eval_date`, §3.1)
com valor de mercado — **excluindo** posições abertas sem preço (§2.1).

#### `portfolio_targets`
```sql
CREATE TABLE portfolio_targets (
  category     TEXT PRIMARY KEY,        -- "acoes", "etf", "fii", "rf", "cripto", "aposentadoria"
  target_pct   NUMERIC(5,2) NOT NULL,   -- % alvo (ex: 50.00 para 50%)
  updated_at   TIMESTAMPTZ DEFAULT now()
);
```

#### `asset_prices`
```sql
CREATE TABLE asset_prices (
  ticker       TEXT NOT NULL,
  price_brl    NUMERIC(20,8) NOT NULL,
  price_usd    NUMERIC(20,8),           -- para cripto
  source       TEXT NOT NULL,           -- "brapi", "coingecko", "binance", "manual"
  is_manual    BOOLEAN DEFAULT false,
  fetched_at   TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (ticker)                  -- upsert por ticker, manter último
);
```

#### `wallet_positions`
```sql
CREATE TABLE wallet_positions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  wallet       TEXT NOT NULL,           -- "etherscan", "solscan", "liquid", "binance", "kucoin"
  address      TEXT,
  ticker       TEXT NOT NULL,
  quantity     NUMERIC(20,8) NOT NULL,
  scanned_at   TIMESTAMPTZ NOT NULL,
  is_manual    BOOLEAN DEFAULT false
);
CREATE INDEX idx_wallet_pos_ticker ON wallet_positions(ticker);
```

#### `goals`
```sql
CREATE TABLE goals (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL,           -- "Reserva de Emergência", "Liberdade Financeira"
  target_brl   NUMERIC(15,2) NOT NULL,  -- ex: 50872.00
  formula      TEXT,                    -- descrição da fórmula usada
  notes        TEXT,
  created_at   TIMESTAMPTZ DEFAULT now()
);
```

#### `benchmark_data`
```sql
CREATE TABLE benchmark_data (
  date         DATE NOT NULL,
  cdi_daily    NUMERIC(10,8),           -- taxa CDI over do dia
  ipca_monthly NUMERIC(10,8),           -- IPCA do mês (null para dias não-finais)
  ibov_close   NUMERIC(15,2),
  PRIMARY KEY (date)
);
```

#### `active_alerts`
```sql
CREATE TABLE active_alerts (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type         TEXT NOT NULL,           -- "rebalancing", "concentration", "defi_expiry", "ir_crypto", "fixed_cost"
  severity     TEXT NOT NULL,           -- "info", "warning", "critical"
  title        TEXT NOT NULL,
  message      TEXT NOT NULL,
  data         JSONB,                   -- detalhes específicos do alerta
  is_read      BOOLEAN DEFAULT false,
  created_at   TIMESTAMPTZ DEFAULT now(),
  expires_at   TIMESTAMPTZ             -- null = permanente até resolver
);
```

### 3.3 Views derivadas

```sql
-- Posição atual por ativo (calculada em Python, mas disponível como view auxiliar)
CREATE VIEW positions AS
SELECT
  ticker,
  category,
  SUM(CASE WHEN op_type = 'buy' THEN quantity ELSE -quantity END) AS quantity_net,
  SUM(CASE WHEN op_type = 'buy' THEN total_amount ELSE 0 END) /
    NULLIF(SUM(CASE WHEN op_type = 'buy' THEN quantity ELSE 0 END), 0) AS avg_price,
  SUM(CASE WHEN op_type IN ('buy','sell') THEN
    CASE WHEN op_type = 'buy' THEN -total_amount ELSE total_amount END
    ELSE 0 END) AS net_invested
FROM asset_operations
WHERE op_type IN ('buy', 'sell')
GROUP BY ticker, category;

-- Resumo mensal de caixa
CREATE VIEW monthly_summary AS
SELECT
  date_trunc('month', date) AS month,
  SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS total_income,
  SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) AS total_expense,
  SUM(amount) AS net_cashflow,
  CASE WHEN SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) > 0
    THEN SUM(amount) / SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) * 100
    ELSE 0 END AS savings_rate
FROM transactions
GROUP BY date_trunc('month', date)
ORDER BY month DESC;
```

---

## 4. Design de API

### 4.1 Convenções

- Prefixo: `/api/v1/`
- Auth: `Authorization: Bearer <JWT>` em todos os endpoints (exceto `/auth/login`)
- Respostas de erro: `{ "error": "code", "message": "descrição", "detail": {} }`
- Paginação: `?page=1&limit=50` para listas
- Timestamps: ISO 8601 com timezone (UTC)

### 4.2 Endpoints por engine

#### Auth
```
POST   /api/v1/auth/login           # { email, password } → { access_token, expires_in }
POST   /api/v1/auth/refresh         # { refresh_token } → { access_token }
```

#### Ledger
```
GET    /api/v1/transactions         # lista paginada, filtros: ?from=&to=&category=&account_id=
POST   /api/v1/transactions         # criar transação
PUT    /api/v1/transactions/{id}    # editar
DELETE /api/v1/transactions/{id}    # deletar
GET    /api/v1/cashflow             # fluxo de caixa com saldo running
GET    /api/v1/cashflow/summary     # resumo mensal (view monthly_summary)
GET    /api/v1/cashflow/projection  # projeção 30/60/90 dias
GET    /api/v1/accounts             # lista de contas
POST   /api/v1/accounts             # criar conta
GET    /api/v1/fixed-costs          # lista de custos fixos
POST   /api/v1/fixed-costs          # criar custo fixo
```

#### Portfolio
```
GET    /api/v1/portfolio/positions      # posições atuais (view + preços do market engine)
GET    /api/v1/portfolio/operations     # histórico de operações paginado
POST   /api/v1/portfolio/operations     # registrar compra/venda/rendimento
GET    /api/v1/portfolio/allocation     # % atual vs % meta por categoria
GET    /api/v1/portfolio/rebalancing    # sugestão de aporte dado valor de entrada ?amount=
GET    /api/v1/portfolio/xirr           # XIRR consolidado e por categoria
GET    /api/v1/portfolio/ir-estimate    # estimativa de IR por categoria
```

#### Market
```
GET    /api/v1/market/prices            # preços atuais de todos os ativos em carteira
GET    /api/v1/market/prices/{ticker}   # preço de um ativo específico
POST   /api/v1/market/prices/{ticker}   # atualizar preço manual (RF privada, DeFi)
GET    /api/v1/market/wallets           # posições on-chain escaneadas
GET    /api/v1/market/refresh           # forçar atualização de preços (admin)
```

#### Analytics
```
GET    /api/v1/analytics/summary        # XIRR, benchmarks, retorno real, drawdown
GET    /api/v1/analytics/benchmarks     # CDI/IPCA/IBOV no período de investimento
GET    /api/v1/analytics/projection     # projeções em 3 cenários
GET    /api/v1/analytics/goals          # progresso das metas (Reserva, LF)
GET    /api/v1/analytics/goals/{id}     # detalhe de uma meta com projeção
```

#### Alertas
```
GET    /api/v1/alerts                   # alertas ativos
PUT    /api/v1/alerts/{id}/read         # marcar como lido
DELETE /api/v1/alerts/{id}             # dispensar alerta
```

#### Hermes (endpoints de integração)
```
GET    /api/v1/hermes/resumo-geral      # snapshot completo (auth: Hermes service token)
GET    /api/v1/hermes/alertas           # alertas ativos simplificados
GET    /api/v1/hermes/portfolio/xirr    # XIRR atual
POST   /api/v1/hermes/expenses          # registrar despesa
POST   /api/v1/hermes/income            # registrar receita
```

---

## 5. Autenticação e segurança

### Fluxo JWT
1. `POST /auth/login` → backend valida credencial (Supabase Auth ou senha hasheada no DB) → retorna `access_token` (15min) + `refresh_token` (30 dias)
2. Frontend armazena `access_token` em memória (não em localStorage) e `refresh_token` em httpOnly cookie
3. Hermes usa um `service_token` separado com escopo limitado ao prefixo `/hermes/`

### Segurança
- Secrets: env vars via Fly.io secrets (nunca em código ou `.env` commitado)
- CORS: origem permitida apenas `goodies.vercel.app` (+ `localhost` em dev)
- Rate limiting: FastAPI + slowapi por IP: 100 req/min geral, 10 req/min para endpoints de escrita
- Logs: sem dados financeiros em texto plano — logar apenas IDs e tipos de operação
- Supabase RLS: Row Level Security ativado por segurança em camadas (mesmo sendo single-user)

---

## 6. Padrão de cache (Redis)

```python
# Interface de cache — todos os fetchers usam este padrão
class PriceCache:
    def get(self, key: str) -> Optional[PriceData]:
        """Retorna None se expirado ou não existe."""
    
    def set(self, key: str, data: PriceData, ttl_seconds: int):
        """Salva com TTL. Também persiste em asset_prices (backup)."""
    
    def get_or_fetch(self, key: str, fetcher: Callable, ttl: int) -> PriceData:
        """Cache-aside: tenta cache, se miss → fetch → salva → retorna."""
```

**Estratégia de fallback:** se Redis indisponível → consultar `asset_prices` no Postgres (último valor salvo). Se Postgres sem dado recente → retornar `{ value: null, stale: true, last_updated: null }`. Nunca retornar erro 5xx por falta de preço.

---

## 7. Cálculos financeiros críticos

### XIRR
```python
# engines/portfolio/xirr.py
from scipy.optimize import brentq
import numpy as np
from datetime import date

def xirr(cashflows: list[tuple[date, float]]) -> float:
    """
    cashflows: lista de (data, valor) onde:
      - valor < 0 = saída (compra)
      - valor > 0 = entrada (venda, rendimento, ou posição atual)
    Retorna taxa anualizada como decimal (ex: 0.12 para 12% a.a.)
    """
    dates, amounts = zip(*cashflows)
    days = [(d - dates[0]).days for d in dates]
    
    def npv(rate):
        return sum(amt / (1 + rate) ** (d / 365) for amt, d in zip(amounts, days))
    
    return brentq(npv, -0.999, 100.0, xtol=1e-6)
```

**Testes obrigatórios:** comparar resultado com Excel XIRR nos dados reais do portfólio antes de ir a produção.

### Rebalanceamento
```python
def suggest_rebalancing(positions: dict, targets: dict, contribution: float) -> dict:
    """
    Dado o portfólio atual (valor por categoria) e alvos percentuais,
    distribui 'contribution' para minimizar distância do alvo.
    Apenas aporta em categorias abaixo do alvo — nunca vende.
    """
    total = sum(positions.values()) + contribution
    gaps = {cat: targets[cat]/100 * total - positions.get(cat, 0) for cat in targets}
    positive_gaps = {cat: gap for cat, gap in gaps.items() if gap > 0}
    total_gap = sum(positive_gaps.values())
    
    if total_gap == 0:
        return {}
    
    return {cat: contribution * gap / total_gap for cat, gap in positive_gaps.items()}
```

---

## 8. Integração com APIs externas

### BRAPI.dev (B3)
```
GET https://brapi.dev/api/quote/{TICKER}?token={API_KEY}
```
- Remover sufixo `F` de ações fracionárias antes da consulta: `PETR4F` → `PETR4`
- Retry: 3 tentativas com backoff exponencial (1s, 2s, 4s)
- TTL cache: 4h

### CoinGecko (cripto)
```
GET https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=brl,usd
```
- Mapa de IDs: BTC=`bitcoin`, ETH=`ethereum`, SOL=`solana`, PENDLE=`pendle`, HYPE=`hyperliquid` — manter em config (não hardcoded)
- Rate limit free tier: 10–30 calls/min → cache agressivo TTL 2h
- TTL cache: 2h

### Binance API
```
GET https://api.binance.com/api/v3/account   # spot balances (signed)
GET https://api.binance.com/sapi/v1/simple-earn/flexible/position  # earn
```
- Assinar requests com HMAC-SHA256 (api_key + secret_key)
- **Nunca chamar on-demand** — apenas via cron (3× ao dia: 8h, 14h, 20h)
- Armazenar resultado em `wallet_positions` com timestamp

### BCB (benchmarks)
```
GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SERIE}/dados?formato=json&dataInicial={}&dataFinal={}
# CDI: série 11
# IPCA: série 433
```
- Dados históricos: importar bootstrap completo (jul/2024 → hoje) na inicialização do m5
- Depois: atualizar diariamente

### Blockstream Liquid
```
GET https://blockstream.info/liquid/api/address/{ADDRESS}/utxo
```
- Diferente do mainchain: endpoint `/liquid/` é obrigatório
- L-BTC (Liquid Bitcoin) — converter para BTC para exibição

---

## 9. Deployment

### Fly.io (FastAPI)
```toml
# fly.toml
[build]
  dockerfile = "api/Dockerfile"

[env]
  PORT = "8080"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80
  
  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

[mounts]
  # sem volume persistente — tudo no Supabase

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 256    # suficiente para single-user
```

**Workers (APScheduler):** rodam no mesmo processo FastAPI (startup event). Para o MVP, não vale o overhead de um processo separado.

### Vercel (Next.js)
- Deploy automático via GitHub Actions em merge para `main`
- Variáveis de ambiente: `NEXT_PUBLIC_API_URL` apontando para Fly.io

### Supabase
- Projeto: single região (sa-east-1 — São Paulo)
- Extensions necessárias: `pg_stat_statements` (performance)
- Backups: Supabase free tier inclui backups diários por 7 dias

### Redis (Upstash)
- Região: us-east-1 (mais próxima disponível do Fly.io)
- Plano free: 10.000 comandos/dia — suficiente para uso monousuário com cron a cada 2-4h
- Conexão via `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN`

---

## 10. Observabilidade (m6)

| Componente | Ferramenta | O que monitorar |
|---|---|---|
| Logs estruturados | Python `structlog` | Cada fetch de API externa, cada cálculo XIRR, cada alerta disparado |
| Erros | Sentry (free tier) | Exceptions não tratadas, falhas de fetch de API |
| Métricas | Fly.io built-in | CPU, memória, latência de requests |
| Notificação | Discord via Hermes | Alertas de sistema (worker falhou, API externa inacessível > 2h) |

---

## 11. Fluxo de desenvolvimento por milestone

| Milestone | Entregável | Gate |
|---|---|---|
| **m0-foundation** | FastAPI + Next.js + Supabase + Redis rodando, auth JWT, CI/CD | Health check `/api/v1/health` retorna 200 |
| **m1-ledger** | CRUD transações, cálculos de caixa, projeção | Taxa de poupança calculada corretamente vs planilha |
| **m2-portfolio** | CRUD operações, posições, XIRR, rebalanceamento | XIRR bate com Excel nos dados históricos |
| **m3-market-data** | Workers de preço, B3, cripto, Tesouro | Preços atualizando automaticamente sem erro |
| **m4-broker-integration** | Binance API, wallet scan, Liquid | Posições cripto sem entrada manual |
| **m5-analytics** | Benchmarks, projeções, metas, alertas | Dashboard de analytics completo |
| **m6-observability** | Sentry, structlog, alertas Discord | Falha de worker notifica no Discord < 5min |
| **m7-frontend** | Dashboard polido, todas as telas | Vitor fecha a planilha |

---

## 12. Considerações de migração de dados

A planilha atual tem ~400 operações de investimento (22 meses) e ~500 transações de caixa/ano. A migração é **manual e incremental**:

1. **m1:** exportar colunas do FLUXO DE CAIXA como CSV → importar via script Python → validar saldo final contra planilha
2. **m2:** exportar OPERAÇÕES como CSV → importar, calcular XIRR Python, comparar com Excel → só seguir se XIRR coincidir (tolerância < 0.1pp)
3. **Dados manuais (Flash Debênture, CDB Guanabara):** inserir diretamente via UI como `asset_operation` do tipo "buy" com preço atual manual

Não haverá migração automatizada no MVP. A validação por amostragem é obrigatória antes de deprecar a planilha.

---

*→ [[01_PRD]]*
*→ [[03_Stack]]*
*→ [[07_Decisoes]]*
*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*
