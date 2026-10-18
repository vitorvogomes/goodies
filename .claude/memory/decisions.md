# Decisões Arquiteturais — Goodies (ADRs condensados)

> Estas decisões NÃO são negociáveis durante a implementação.
> Se precisar mudar alguma, criar novo ADR em `docs/07_Decisoes.md` e discutir.

---

## ADR-001 — Stack (LOCKED)
FastAPI + Next.js 16 + Supabase (Postgres 15) + Redis (Upstash).
**Emenda 2026-10-17:** Fly.io e Vercel removidos (workflow, `fly.toml`, `DEPLOY.md`). Sem deploy: a v2.0 roda só em localhost; a infra de deploy será desenhada do zero na v2.1.
**Não mudar sem ADR aprovado.** (Frontend atualizado de Next 14 → 16 / React 19 / Tailwind v4 por ADR-009.)

## ADR-002 — XIRR é a métrica de retorno
- Implementação: `scipy.optimize.brentq` em `api/engines/portfolio/xirr.py`
- Compra = cashflow negativo. Venda/rendimento/posição atual = positivo.
- Retorna taxa anualizada decimal (0.0853 = 8,53% a.a.)
- **PROIBIDO** usar `(resultado-aplicado)/aplicado` em qualquer lugar do código

## ADR-003 — APScheduler (não Celery)
Workers de preço e alertas rodam no mesmo processo FastAPI via APScheduler.
Inicializados no `startup` event. Workers devem ser **idempotentes**.

## ADR-004 — Dados manuais nunca bloqueam
Ativos sem API (Flash Debênture, CDB, DeFi): `is_manual=True` em `asset_prices`.
Fallback: Redis → Postgres (`asset_prices`) → manual.
Retorno quando sem dado: `{"value": null, "stale": true, "last_updated": null}` — NUNCA 5xx.

## ADR-005 — Liquid Network: client dedicado
Base URL: `https://blockstream.info/liquid/api` (NÃO `/btc/api`)
Asset IDs: `${LBTC_ASSET_ID}` (L-BTC) + `${LUSDT_ASSET_ID}` (L-USDT) — Liquid é multi-asset.
**Proibido reutilizar qualquer código do fetcher Bitcoin mainchain.**

## ADR-006 — Auth JWT no FastAPI (não Supabase Auth)
- `python-jose` para JWT, `passlib[bcrypt]` para senhas
- Access token: 15min, em memória React (não localStorage)
- Refresh token: 30 dias, httpOnly cookie
- Hermes service token: scope `hermes`, 90 dias, endpoints `/hermes/*`
- **Ignorar qualquer sugestão de usar Supabase Auth para login.**

## ADR-007 — Hermes é opcional
Goodies funciona 100% sem Hermes. Endpoints `/hermes/*` são somente-leitura/escrita
via service token. Hermes não faz login.

## ADR-008 — XIRR calculado em Python, não SQL
Cache Redis TTL 1h. Invalidar cache ao inserir nova operação em `asset_operations`.
Sem função PL/pgSQL para XIRR.

## ADR-009 — Frontend Next.js 16 / React 19 / Tailwind v4
Atualiza a cláusula "Next 14" do ADR-001. Tailwind v4 é CSS-first (`@theme` em `globals.css`,
sem `tailwind.config.ts`); middleware → `proxy.ts`; React Compiler on. Ver `docs/07_Decisoes.md`.

## ADR-010 — Deps do backend com uv (não pip/requirements)
`pyproject.toml` é a **fonte única** (runtime em `[project.dependencies]`, ferramentas em
`[dependency-groups].dev`); `uv.lock` fixa versões. `[tool.uv] package=false` → app roda do
código-fonte (`pythonpath="."`), sem build de wheel. **Sem `requirements*.txt`/`pip`.**
Rodar: `uv sync` (instala), `uv run <ruff|mypy|pytest|uvicorn|alembic>`. Dockerfile/CI usam uv.

## ADR-011 — Caixinha/RDB Nubank = investment net (não receita); Santander externo
> **Superado em parte pelo ADR-015 (2026-10-17):** resgate passa a ser receita. Seguem valendo: caixinhas/CDB
> como ativos RF, reclassificação in-place/idempotente, NÃO rodar `reset_ledger.py`, Santander externo.
Decidido na faxina pré-m3 (2026-06-06). Ver `docs/v1/11_Coerencia_Nubank_Portfolio_pre_m3.md`.
- **Aplicação E resgate de caixinha são `kind='investment'`** (o resgate volta positivo e neta o
  `total_invested`). Resgate de caixinha **nunca** é `income` — inflaria a taxa de poupança.
- Reclassificação de linhas curadas é **in-place/idempotente** (`api/scripts/oneoff/reclassify_caixinhas.py`).
  **NÃO rodar `api/scripts/oneoff/reset_ledger.py`** no banco curado — apagaria a curadoria. A migration
  `0009` cuida só das regras de import **futuro**.
- Caixinhas/CDB Nubank são ativos `asset_category='Renda Fixa'` (registro config-driven em
  `engines/portfolio/caixinhas.py`; **Reserva** já listada, `enabled=False` até criar). Valoração
  pós-fixada via `rf_cdi.py` com `settings.cdi_anual` (env `CDI_ANUAL`, provisório até o m5/BCB) —
  cobre o ADR-004 (`is_manual=true`, worker m3 não sobrescreve).
- **Santander = conta externa:** Pix do próprio nome vindos do Santander (~R$32k em `income/Extra`)
  contam como receita/despesa externa — **não** transferência interna (decisão reafirmada).

## ADR-012 — Market Engine (m3): endpoints, precedência de preço, fontes free-tier
Decidido no m3 (2026-06-06). Ver `docs/v1/12_Gate_M3_Market.md` + `docs/15_Debito_Tecnico.md`.
- **Preços sob `/api/v1/market/*`** (não `/portfolio`). `POST /market/prices/{ticker}` (manual),
  `GET /market/prices[/{ticker}]` (leitura via fallback). O antigo `PUT /portfolio/prices` foi
  **removido**. Contrato Pydantic (`PriceOut`) — superfície nova do m3.
- **`portfolio.service.upsert_price` é o chokepoint único de escrita de preço.** Precedência
  **`is_manual`**: worker (`is_manual=false`) NUNCA sobrescreve linha manual (Flash/RF/caixinhas/
  DeFi — sem fonte de mercado); manual sempre vence. Invalida o cache de XIRR (ADR-008) **e** o
  cache Redis de preço dentro do fluxo de escrita. `is_manual=true` ⇒ preço nunca fica `stale`.
- **Fontes free-tier (cadência DIÁRIA p/ B3/Tesouro):** BRAPI grátis = **1.000 req/mês, 1 ativo/
  req** (sem batch) → `price_b3` 1×/dia útil 19h BRT (~350/mês). **Tesouro via Tesouro Transparente
  CSV** (open data CKAN, sem auth/WAF/quota) — a API oficial do Tesouro Direto está atrás de
  Cloudflare (403 headless) e o brapi v2/treasury é Pro-only. CoinGecko demo = 10k/mês (*/2h).
  `ttl_b3=ttl_tesouro=26h` p/ o preço do dia não aparecer "desatualizado". `EVALUATION_DATE` (§3.1)
  threada a data de avaliação única. **Cripto/Binance só via cron — m4.**

## ADR-013 — Wallet scan (m4): fontes, `source` p/ sweep, valoração manual/DeFi
Decidido no m4 (2026-06-07). Ver `docs/07_Decisoes.md` + memória `m4-wallet-scan-config`/`m4-hype-on-hyperliquid`.
- **6 fetchers fail-soft** (Etherscan ETH/ARB/PENDLE, Hyperliquid, Solana, Liquid, Bitcoin, Binance);
  sem credencial = no-op. **HYPE em 2 fontes** no mesmo endereço Rabby: L1 spot (Info API) + **HyperEVM
  nativo** (`eth_getBalance`, `HYPEREVM_RPC_URL`). HyperEVM entra em escopo **só p/ o HYPE nativo**.
- **O `source` (por fonte) controla o sweep** (snapshot-replace): cada (sub)fonte usa um `source`
  próprio — `hyperliquid` (spot) ≠ `hyperevm` — p/ que a queda de uma NÃO varra o snapshot bom da
  outra (outage ≠ posição fechada).
- **Posições manuais** (`is_manual=true`, p/ Liquid confidencial): o sweep nunca as apaga e elas
  nunca ficam `stale`. Editáveis inline na UI (upsert).
- **Valoração manual/DeFi** reusa o preço do m3 via aliases em `coingecko_ids` (chave UPPER). Cuidado:
  **id da API CoinGecko ≠ slug do site** (`susdai`, não `staked-usdai`); YT-xSOL sem fonte (decisão).
- **Reconciliação é só cripto** (`reconcile` filtra `asset_operations` por `CRYPTO_CATEGORIES`); B3 e
  caixinhas Nubank vêm por outra via, não pelo scan de carteira.

---

## ADR-014 — v2.0 só em localhost (sem deploy, sem CI)
Decidido 2026-10-17 (commit d3748a4). Fly.io, Vercel e GitHub Actions removidos. A v2.0 roda só local
(`docker compose` + `pnpm dev`); nenhum host de nuvem recebe dado financeiro. Backup local diário
(`pg_dump`, fora do repo). Infra de deploy desenhada do zero na v2.1. Ver spine AD-18.

## ADR-015 — Resgate é receita (reverte o ADR-011 nesse ponto)
Decidido no PRD v2 (2026-10-17). Resgate de caixinha/RF/corretora é receita, exibido em linha própria e
reclassificado em todo o histórico (FR-19, migração idempotente). A taxa de poupança usa a **receita do
trabalho** (sem resgates), então o gate jun/2026 = 55,48% continua válido. Ver spine AD-6/AD-7/AD-16.

## Endereços de wallet (via `.env` — NÃO hardcodar)

> Valores reais ficam SÓ em `.env` (gitignored). Aqui e em todos os docs
> usamos apenas os nomes das variáveis. Ver `.claude/memory/security.md`.

| Rede / ativos | Wallet | Endereço (env) |
|---|---|---|
| ETH/ARB/PENDLE + HYPE (L1 spot + HyperEVM) | Rabby | `${WALLET_RABBY_ADDRESS}` |
| SOL | Phantom | `${WALLET_PHANTOM_SOL_ADDRESS}` |
| Liquid (L-BTC + L-USDT) | SideSwap | `${WALLET_SIDESWAP_ADDRESS}` — confidencial → entrada manual |
| BTC (mainchain) | Trust | `${WALLET_TRUST_BTC_ADDRESS}` |

Config não-endereço (também `.env`): `LBTC_ASSET_ID`, `LUSDT_ASSET_ID`, `LIQUID_BASE_URL`,
`BTC_BASE_URL`, `SOLANA_RPC_URL`, `HYPEREVM_RPC_URL`, `ETHERSCAN_API_KEY`, `BINANCE_API_KEY`/`_SECRET`.

## TTLs de cache Redis

| Dado | TTL |
|---|---|
| B3 (BRAPI) | 26h — 1×/dia útil 19h (free-tier) |
| Cripto (CoinGecko) | 2h |
| Tesouro Direto | 26h — 1×/dia útil |
| Wallet scan | 14h — scan 3×/dia (8/14/20h), TTL > gap noturno |
| Benchmarks (CDI/IPCA/IBOV) | 24h |
| XIRR calculado | 1h (invalidar em nova operação) |

## Chave de nomes Redis

`{engine}:{type}:{identifier}`
Ex: `price:b3:PETR4`, `price:crypto:BTC`, `wallet:binance:spot`, `xirr:consolidated`
