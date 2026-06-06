# Gate m3 — Market Engine (preços automáticos)

**Critério (CLAUDE.md):** preços B3 e cripto atualizando automaticamente via worker, **sem
erro por 48h**; o dashboard/posições mostram valor de mercado sem entrada manual.

O código está completo e testado (suite 303 verde; fetchers BRAPI/CoinGecko validados ao
vivo). O gate em si é **operacional** — depende de deixar os workers rodando no ambiente do
Vitor e observar 48h sem exceção.

---

## Pré-condições

1. **Tokens no `.env`** (raiz): `BRAPI_TOKEN`, `COINGECKO_API_KEY` (já presentes). `REDIS_URL`
   vazio → cai para `redis://localhost:6379/0` (docker local).
2. **`enable_scheduler=true`** (default) e **`environment != "test"`**. Sob `uvicorn`/docker o
   lifespan inicia o `AsyncIOScheduler` (jobs `price_b3` e `price_crypto`).
3. **Destravar o refresh de B3** (importante): os preços B3 atuais foram semeados com
   `is_manual=true` (versão antiga do `import_b3`). Pela precedência §3.4 o worker (`is_manual=false`)
   **não sobrescreve** linha manual — então re-rodar `import_b3` **não basta** (também é bloqueado).
   O flip é feito por um script dedicado, idempotente (só toca os tickers cotáveis Ações/ETFs/FIIs):
   ```
   DATABASE_URL=postgresql://goodies:goodies@localhost:5432/goodies \
     uv run python ../scripts/enable_market_pricing.py            # dry-run
   DATABASE_URL=... uv run python ../scripts/enable_market_pricing.py --commit
   ```
   Preços genuinamente manuais (Flash/caixinhas/CDB Guanabara `nubank-cdi`/`flash-pre`, e Tesouro
   enquanto o fetcher não roda em prod) permanecem `is_manual=true` e **nunca** são tocados pelo
   worker — comportamento desejado. **Executado em 2026-06-06:** 14 tickers B3 destravados + worker
   rodado ao vivo → 16/16 cotados via BRAPI (`is_manual=false`).

> ⚠️ **Guardrail:** NÃO rodar `scripts/reset_ledger.py` no banco curado (ADR-011).

---

## Cadência dos workers

| Worker | Cron | Cobre | TTL cache |
|---|---|---|---|
| `price_b3` | **1×/dia útil, 19:00 America/Sao_Paulo** (após fechamento) | Ações/ETFs/FIIs (BRAPI) + Tesouro | 26h / 6h |
| `price_crypto` | a cada 2h, todo dia | Cripto (CoinGecko) | 2h |

**Limites free-tier (revisado):** BRAPI grátis = **1.000 req/mês, 1 ativo/req** (sem batch) →
~16 tickers × 1×/dia útil ≈ **350/mês** (3×/dia estouraria). `ttl_b3=26h` p/ o preço de
fechamento não aparecer "desatualizado" durante o dia. CoinGecko demo = **10k/mês**, 1 call/run
(batch de ids) → */2h trivial. (PETR4 é um dos 4 tickers-teste ilimitados do BRAPI — bônus menor.)

Cache key `price:{tipo}:{ticker}`; fallback Redis → Postgres `asset_prices` → null/stale.
Falha de API externa nunca vira 5xx (fail-soft); o símbolo é omitido e o valor anterior fica.

---

## Verificação rápida (sem esperar 48h)

- **Suite de integração:** `uv run pytest tests/market/ -q` (workers → Postgres/Redis → endpoints,
  precedência is_manual, API-down → stale). Cadência do scheduler coberta sem viajar no tempo.
- **Smoke ao vivo dos fetchers** (precisa rede + tokens):
  - BRAPI: `BrapiFetcher().fetch(["PETR4"])` → preço ≠ vazio. **OK no sandbox.**
  - CoinGecko: `CoinGeckoFetcher().fetch(["BTC"])` → BRL+USD. **OK no sandbox.**
  - Tesouro: `TreasuryFetcher().fetch(["Tesouro Selic 2029"])` → preço. **403 no sandbox (WAF/IP);
    validar no ambiente do Vitor.** A API exige cabeçalhos de navegador (já enviados); se ainda 403,
    é bloqueio de IP do datacenter.
- **Disparo manual imediato** (sem esperar o cron): registrar um job com `next_run_time=now`, ou
  chamar o corpo direto:
  ```python
  from db.connection import init_pool, get_pool
  from workers.price_workers import run_price_b3, run_price_crypto
  await init_pool(); print(await run_price_b3(get_pool())); print(await run_price_crypto(get_pool()))
  ```
  Conferir `SELECT ticker, source, is_manual, fetched_at FROM asset_prices ORDER BY fetched_at DESC`.

## Critério de PASS das 48h

Com os workers rodando no ambiente do Vitor por 48h:
- `asset_prices.fetched_at` dos tickers B3/cripto **avança** a cada ciclo (não fica preso);
- **zero exceção não tratada** nos logs dos jobs (`logger "goodies.workers"`);
- `GET /api/v1/market/prices` mostra os ativos B3/cripto `stale=false`/`is_manual=false`, e os
  manuais (RF) intactos;
- dashboard/posições refletem valor de mercado sem edição manual.

(Observabilidade formal — Sentry/Discord em falha de worker — é o m6.)
