# SESSION m4-broker-integration — Prompt de inicialização

**Data de referência:** 2026-06-06
**Branch:** criar `m4-broker` a partir de `main` (após mergear `m3-market` → `main`)
**Milestone:** m4 — Broker Integration (escaneamento on-chain + Binance + DeFi)
**Gate de saída (CLAUDE.md):** posições cripto **escaneadas automaticamente** (sem entrada manual).

---

## Estado atual (o que já existe — NÃO refazer)

✅ **m3 Market Engine fechado** (12/12 + gate validado ao vivo). Preços **100% automáticos** para
23 ativos: 16 B3 (BRAPI) + 7 Tesouro (Tesouro Transparente CSV). Só 4 manuais (Flash-Debênture +
caixinhas/CDB Nubank). Suite **308 verde**; ruff + mypy strict; `npm build` 16 rotas.

✅ Scaffolding que o m4 vai **estender, não recriar**:
- **Fetchers + base:** `api/engines/market/fetchers/{base,brapi,coingecko,treasury}.py`. `base.py`
  tem `PriceFetcher` (Protocol), `PriceQuote`, `with_retry` (backoff 1/2/4, sleep injetável).
  **O fetcher de cripto (CoinGecko, BRL+USD) já existe** — o m4 fornece as QUANTIDADES (saldo
  on-chain) e reusa o preço.
- **Workers + scheduler:** `api/workers/{price_workers,scheduler}.py` (APScheduler no lifespan,
  `CronTrigger` tz `America/Sao_Paulo`, `coalesce/max_instances=1`, guard `environment!=test`+
  `enable_scheduler`). `run_price_crypto` (*/2h) já roda — fica no-op até existir holding cripto.
- **Chokepoint de preço:** `portfolio.service.upsert_price` (precedência `is_manual`); fallback
  `market.service.get_price` (Redis→Postgres→null/stale, nunca 5xx); `cache_aside_write`.
- **Endpoints:** `/api/v1/market/*` (Pydantic `PriceOut`). Tela `/market` + `/positions` (preço
  auto bloqueado 🔒). Padrão de UI reutilizável.
- `.env` já tem (todos SET): `ETHERSCAN_API_KEY`, `SOLSCAN_API_KEY`, `BINANCE_API_KEY/SECRET`,
  `WALLET_EVM_ADDRESS`, `WALLET_SOL_ADDRESS`, `WALLET_LIQUID_ADDRESS`, `LIQUID_BASE_URL`, `LBTC_ASSET_ID`.

---

## ⚠️ PRÉ-REQUISITOS EMBUTIDOS (B0 do m4 — do `docs/13_Debito_Tecnico_m3.md`)

**Resolver ANTES de escrever os 5 fetchers de wallet** (Etherscan/Solscan/Liquid/Binance/BCB):

1. **[🟡 #1] Fatorar a base dos fetchers.** Os 3 fetchers do m3 repetem "client próprio-ou-injetado
   + `with_retry` + fail-soft". O m4 adiciona **5 fetchers** — extrair um `_fetch(do_request)` (ou
   base class / async-ctxmanager) em `fetchers/base.py` ANTES, senão a duplicação multiplica.
2. **[🟡 #2] `market.service.list_user_prices` é N+1.** Trocar o loop de `get_price` por um
   `SELECT ... WHERE ticker = ANY($1)` + Redis MGET. O m4 cresce a carteira (cripto/wallets).
3. **[🟡 #3] XIRR flusha o cache toda rodada de worker.** `upsert_price` invalida o XIRR mesmo sem
   o preço mudar. Invalidar só quando `price_brl`/`price_usd` realmente mudou.

Itens ⚪ menores (rastrear, não bloqueiam): ver `docs/13` (reuso de parsers, source do Tesouro no
import_b3, CSV bufferizado, script vs migration, multi-user/§3.7, DCA duplicado/§3.8).

---

## Escopo do m4 (EPIC-04) + sequência recomendada

Stories (PROGRESS.md `## Milestone m4`): 04-01 a 04-12.

```
B0 (FUNDAÇÃO): base de fetcher (#1) + batch list_user_prices (#2) + XIRR só-quando-muda (#3)
   ↓
B1: 04-01 schema wallet_positions + worker scaffold
   ↓
B2: 04-02 Etherscan (ETH/ARB/HYPE)  +  04-03 Solscan (SOL)  +  04-04 Liquid (ADR-005!)
   ↓
B3: 04-05 Binance (spot + earn, HMAC-SHA256, CRON ONLY)  +  04-06 worker wallet_scan (3×/dia + fallback)
   ↓
B4: 04-07 worker benchmark_daily (BCB CDI/IPCA + yfinance IBOV)   [interface nasce aqui; uso pleno é m5]
  + 04-08 entrada manual DeFi (Phantom) + 04-09 alertas de vencimento DeFi (30d/7d)
   ↓
B5: 04-10 frontend wallets  +  04-11 reconciliação posição escaneada  +  04-12 testes de integração (mocks dos explorers)
   ↓
GATE m4: posição cripto escaneada automaticamente (saldo on-chain → quantidade → valor via preço m3).
```

**Guardrails do CLAUDE.md (NÃO violar):**
- **ADR-005 Liquid:** client **dedicado** em `fetchers/wallets/liquid.py`, `LIQUID_BASE_URL=.../liquid/api`
  (NÃO `/btc/api`), `LBTC_ASSET_ID` do `.env`. **Proibido reutilizar fetcher Bitcoin mainchain.**
- **Binance/cripto on-demand é proibido — cron only.** Binance assinado (HMAC-SHA256).
- Fail-soft sempre (nunca 5xx por API externa); precedência `is_manual` (worker não toca preço/
  posição manual — DeFi/Phantom é entrada manual, ADR-004). Cache `{engine}:{type}:{id}`.
- APScheduler no mesmo processo (não Celery). TDD obrigatório; `uv run pytest/ruff/mypy` strict.
- Mock dos chain explorers com **respx** (já é dev-dep) nos testes.

---

## Credenciais / fontes (todas já no `.env`)

| Fetcher | Credencial/endereço | Quota free |
|---|---|---|
| Etherscan (ETH/ARB/HYPE) | `ETHERSCAN_API_KEY` + `WALLET_EVM_ADDRESS` | 5 req/s, 100k/dia |
| Solscan (SOL) | `SOLSCAN_API_KEY` + `WALLET_SOL_ADDRESS` | confirmar plano |
| Liquid (L-BTC) | `LIQUID_BASE_URL` + `LBTC_ASSET_ID` + `WALLET_LIQUID_ADDRESS` | API pública Blockstream |
| Binance (spot+earn) | `BINANCE_API_KEY`/`SECRET` (HMAC) | cron only |
| BCB (CDI/IPCA) | API pública SGS | benchmark (mais m5) |

> Confirmar os **endereços de wallet** reais no `.env` antes do B2 (privacidade: PII, gitignored).
> NUNCA imprimir chaves/segredos/endereços no chat.

---

## Referências rápidas
- **Débito técnico (LER PRIMEIRO):** `docs/13_Debito_Tecnico_m3.md`.
- **Decisões (não violar):** `.claude/memory/decisions.md` (ADR-005 Liquid, ADR-012 Market, ADR-004).
- **Market Engine (reusar):** `docs/12_Gate_M3_Market.md`; `engines/market/`.
- **Stack/guardrails:** `CLAUDE.md` (Liquid ADR-005, cache, fallback, cron-only).
- **Memória:** `.claude/memory/` (conventions/decisions/skills) + auto-memory `m3-market-engine`.
- **Progresso:** `PROGRESS.md` (`## Milestone m4`). **Épico:** `docs/05_Epicos/EPIC-04-BrokerIntegration.md`.
- **Guardrail de dados:** **NÃO rodar `reset_ledger`** no banco curado (ADR-011).

---

## Perguntas antes de começar
1. Mergear `m3-market` → `main` agora e abrir `m4-broker` a partir de `main`?
2. Fazer o **B0 (fatorar base de fetcher + N+1 + XIRR cache)** primeiro (recomendado)?
3. Confirmar os endereços de wallet (EVM/SOL/Liquid) e `LBTC_ASSET_ID` no `.env`?
4. DeFi/Phantom é entrada manual (ADR-004) — confirmar quais posições entram assim.

---

*Prompt pronto para colar em sessão nova:*

> Leia `CLAUDE.md`, `PROGRESS.md`, `docs/13_Debito_Tecnico_m3.md` e `SESSION_M4.md`.
> Vamos iniciar o **m4 — Broker Integration**. **Antes dos fetchers de wallet**, faça o **B0**:
> (1) fatorar a base de fetcher (`_fetch`/with_retry) em `fetchers/base.py`; (2) batch no
> `market.service.list_user_prices` (acabar com o N+1); (3) invalidar o cache de XIRR só quando o
> preço muda. Depois os batches B1→B5. Liquid = ADR-005 (client dedicado, `/liquid/api`, nunca
> reusar fetcher Bitcoin). Binance cron-only + HMAC. Fail-soft sempre; TDD; respx nos testes.
> NÃO rodar `reset_ledger`. Atualize o PROGRESS.md ao concluir cada story.
