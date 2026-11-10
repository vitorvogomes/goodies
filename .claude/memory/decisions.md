# Decisões Arquiteturais — Goodies (ADRs condensados)

> Estas decisões NÃO são negociáveis durante a implementação.
> Se precisar mudar alguma, criar novo ADR em `docs/07_Decisoes.md` e discutir.

---

## ADR-001 — Stack (LOCKED)
FastAPI + Next.js 16 + Postgres 15 + Redis 7. Produção no **Railway** (ADR-018); `docker compose` local é o
ambiente de desenvolvimento. Supabase, Upstash, Fly e Vercel não são usados.
**Não mudar sem ADR aprovado.** (Frontend atualizado de Next 14 → 16 / React 19 / Tailwind v4 por ADR-009.)

## ADR-002 — XIRR é a métrica de retorno
- Implementação: `scipy.optimize.brentq` em `api/engines/portfolio/xirr.py`
- Compra = cashflow negativo. Venda/rendimento/posição atual = positivo.
- Retorna taxa anualizada decimal (0.0853 = 8,53% a.a.)
- **PROIBIDO** usar `(resultado-aplicado)/aplicado` em qualquer lugar do código

## ADR-003 — APScheduler (não Celery)
Workers de preço e alertas rodam no mesmo processo FastAPI via APScheduler.
Inicializados no `lifespan` do FastAPI (`main.py`). Workers devem ser **idempotentes**.

## ADR-004 — Dados manuais nunca bloqueam
Ativos sem fonte de mercado nem valoração pelo app (DeFi, token sem cotação): `is_manual=True` em `asset_prices`.
Na v2 a debênture vale pelo fator mensal (Story 7.6) e a RF pelo CDI publicado + saldos informados (Story 7.4,
`rf_balance_anchors`) — `assets.valuation` diz qual; todo valor sai como `Valued` com `as_of`.
Fallback: Redis → Postgres (`asset_prices`) → manual.
Retorno quando sem dado: `{"value": null, "stale": true, "last_updated": null}` — NUNCA 5xx.

## ADR-005 — Liquid Network: client dedicado
Base URL: `https://blockstream.info/liquid/api` (NÃO `/btc/api`)
Asset IDs: `settings.lbtc_asset_id` (L-BTC) + `settings.lusdt_asset_id` (L-USDT), constantes públicas em `config.py` — Liquid é multi-asset.
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
Rodar: `uv sync` (instala), `uv run <ruff|mypy|pytest|uvicorn|alembic>`. O Dockerfile usa uv (não há CI).

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
  `engines/portfolio/caixinhas.py`). **Na v2:** as operações vêm das transações (Story 7.5; a escolha
  em `transaction_caixinha` vence) e o valor é `portfolio/rf.cdi_value` sobre o CDI diário publicado
  (`benchmark_data`), ancorado nos saldos informados (`rf_balance_anchors`, 0047). Sem constante de CDI.
- **Santander = conta externa:** Pix do próprio nome vindos do Santander (~R$32k em `income/Extra`)
  contam como receita/despesa externa — **não** transferência interna (decisão reafirmada).

## ADR-012 — Market Engine (m3): endpoints, precedência de preço, fontes free-tier
Decidido no m3 (2026-06-06). Ver `docs/v1/12_Gate_M3_Market.md`.
- **Preços sob `/api/v1/market/*`** (não `/portfolio`). `POST /market/prices/{ticker}` (manual),
  `GET /market/prices[/{ticker}]` (leitura via fallback). O antigo `PUT /portfolio/prices` foi
  **removido**. Contrato Pydantic (`PriceOut`) — superfície nova do m3.
- **`market.service.upsert_price` é o chokepoint único de escrita de preço.** Precedência
  **`is_manual`**: worker (`is_manual=false`) NUNCA sobrescreve linha manual (Flash/RF/caixinhas/
  DeFi — sem fonte de mercado); manual sempre vence. Invalida o cache de XIRR (ADR-008) **e** o
  cache Redis de preço dentro do fluxo de escrita. `is_manual=true` ⇒ preço nunca fica `stale`.
- **Fontes free-tier (cadência DIÁRIA p/ B3/Tesouro):** BRAPI grátis = **1.000 req/mês, 1 ativo/
  req** (sem batch) → `price_b3` 1×/dia útil 19h BRT (~350/mês). **Tesouro via Tesouro Transparente
  CSV** (open data CKAN, sem auth/WAF/quota) — a API oficial do Tesouro Direto está atrás de
  Cloudflare (403 headless) e o brapi v2/treasury é Pro-only. CoinGecko demo = 10k/mês (*/2h).
  `ttl_b3=ttl_tesouro=26h` p/ o preço do dia não aparecer "desatualizado". `EVALUATION_DATE` (§3.1)
  threada a data de avaliação única. **Cripto/Binance só via cron — m4.**
- **Na v2:** token cripto sem cotação tem preço manual em US$ (`source='manual_usd'`); o R$ segue a cotação
  do dólar (USDT/USDC) a cada `price_crypto` e o histórico guarda cada dia na cotação do dia.

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
- **Na v2:** Conciliação confere o consolidado B3 + as carteiras (Story 7.9). Só o trilho "B3 (corretoras)"
  guarda caixa (`transit.Rail.holds_cash`); Tesouro, RF Nubank e Flash mostram diferença de conciliação.

---

## ADR-014 — v2.0 só em localhost — SUPERADO pelo ADR-018 (detalhe em `docs/07_Decisoes.md`)

## ADR-015 — Resgate é receita (reverte o ADR-011 nesse ponto)
Decidido no PRD v2 (2026-10-17). Resgate de caixinha/RF/corretora é receita, exibido em linha própria e
reclassificado em todo o histórico (FR-19, migração idempotente). A taxa de poupança usa a **receita do
trabalho** (sem resgates). O gate de 55,48% foi substituído pelo baseline por mês (ADR-016). Ver spine
AD-6/AD-7/AD-16.

## ADR-016 — Base completa até 16/10/2026 e gate de dados pela própria base
Decidido 2026-10-18, a pedido do Vitor ("importar os arquivos de `files/` e fazer os cálculos com base no que temos").
- Os OFX do Nubank (PF jun/2024–16/10/2026, MEI 2025–16/10/2026), a movimentação B3 de jun–out/2026 e as
  integralizações Flash de jul–out/2026 foram importados pelo caminho v1 (dedup por FITID/`operation_hash`).
  A liquidação D+2 que repete negócios já importados por negociação foi descartada (7 operações de 09/06/2026).
  Preços do consolidado B3 de set/2026 aplicados; caixinha Nu Reserva Imediata ativada (desde jul/2026).
- **Transações importadas a partir de 2026-10-18T06:07Z não foram revisadas pelo Vitor.** 128 das 148 sem padrão
  receberam categoria sugerida pelo histórico (Jaccard de tokens ≥ 0,6); 20 seguem "outros". Na Story 2.4 elas
  entram com `category_source = suggestion` (ou `rule` se um padrão casa) e `review_status = pending`, nunca
  `manual`.
- **Gate de dados:** os 55,48% da planilha não são reproduzíveis pela base (jun/2026 completo = 57,46%, com 2
  transações a classificar). O invariante das revisões de dado passa a ser a taxa de poupança **de cada mês igual à
  do baseline fixado** (`tests/dados_reais/pinned_baseline.txt`), salvo os deltas esperados listados no teste da
  revisão. Onde os docs de planejamento dizem "55,48%", leia-se "taxa de jun/2026 do baseline".
- **Desde a Story 2.6** a taxa de referência é a da fórmula v2 (`ledger/calc`, AD-7), fixada em
  `tests/dados_reais/pinned_savings_v2.txt` (jun/2026 = 56,87%); XIRR, aplicado e contagens seguem iguais ao
  `pinned_baseline.txt`.

## ADR-017 — Distribuição do aporte executável (lotes, troco, aportes fixos)
Decidido 2026-10-18 a pedido do Vitor (ver `docs/07_Decisoes.md`). O sugerido por ativo é compra de fato: B3 em
cotas inteiras, Tesouro em 0,01 título com mínimo de R$ 30 (`planning/distribution.Lot`), ao preço de hoje; renda
fixa, caixinhas e cripto ao centavo. Base do plano = valor de hoje menos o que entrou no mês (estável a cada
depósito, mas anda com o mercado). Troco das cotas: reserva até encher → caixinha Turbo até R$ 5 mil (só se a
`caixinha:turbo` estiver ligada à reserva; pode passar do alvo da reserva) → objetivos do mais perto de ser
concluído ao mais longe (travado é pulado; reserva travada pula também a Turbo) → classes livres → sem destino.
Aportes fixos (`fixed_contributions`, 0050: Flash R$ 1.000, Ana Maria R$ 4.000) são trava padrão do mês; a trava
do mês vence. Lista de compras por classe: primeiro os ativos de valor livre (reduzidos em proporção se passarem do
que falta na classe), depois os de lote com o que sobra (cotas do plano − as que entraram; travado/fixo: o R$ que
falta).

## ADR-018 — v2.1 na nuvem: Railway (substitui o ADR-014)
Decidido 2026-11-10 a pedido do Vitor (ver `docs/07_Decisoes.md`, runbook `docs/DEPLOY_RAILWAY.md`).
- Railway, ambiente `production`: Postgres **15** (`postgres-ssl:15`), Redis 7, `api` (root `api/`), `web` (root `web/`).
- **Só o web é público.** O Next repassa `/api/v1/*` para a api pela rede privada (`API_INTERNAL_URL`); api, Postgres e
  Redis sem domínio público. Cookie de refresh e `proxy.ts` na mesma origem (ADR-006 intacto).
- api com 1 réplica, sem dormir (ADR-003). `/docs` e `/openapi.json` desligados em `ENVIRONMENT=production`.
- Migração em produção pela subida (`AUTO_MIGRATE=true`: backup → `upgrade head`); banco vazio faz bootstrap
  `0002_refresh_token_hash` → admin (`ADMIN_EMAIL`/`ADMIN_PASSWORD`, lidos só com banco vazio) → `head`; banco
  parado antes do admin retoma o bootstrap.
- Em produção a subida recusa `DATABASE_URL`/`REDIS_URL` vazias ou em localhost (referência `${{…}}` que não
  resolveu) — nunca cai no padrão de dev em silêncio.
- Backups: volume `/backups` (`db_backup` diário, `restore_check` mensal) + cópia local por `scripts/backup_railway.sh`
  (usa `railway ssh`, que exige chave SSH registrada — quem roda é o Vitor).
- Segredos de produção só nas variáveis do Railway, gerados novos. Banco começa vazio; dump de casa depois.
- O gate `dados_reais`/`migrar` fica pendente até o `pinned_backup` existir nesta máquina.

## Endereços de wallet (via `.env` — NÃO hardcodar)

> Valores reais ficam SÓ em `.env` (gitignored). Aqui e em todos os docs
> usamos apenas os nomes das variáveis. Ver `.claude/memory/security.md`.

| Rede / ativos | Wallet | Endereço (env) |
|---|---|---|
| ETH/ARB/PENDLE + HYPE (L1 spot + HyperEVM) | Rabby | `${WALLET_RABBY_ADDRESS}` |
| SOL | Phantom | `${WALLET_PHANTOM_SOL_ADDRESS}` |
| Liquid (L-BTC + L-USDT) | SideSwap | `${WALLET_SIDESWAP_ADDRESS}` — confidencial → entrada manual |
| BTC (mainchain) | Trust | `${WALLET_TRUST_BTC_ADDRESS}` |

Config não-endereço no `.env`: `SOLANA_RPC_URL`, `HYPEREVM_RPC_URL`, `ETHERSCAN_API_KEY`, `BINANCE_API_KEY`/`_SECRET`.
No código (`config.py`, constantes públicas): asset ids da Liquid e URLs base da Blockstream.

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
