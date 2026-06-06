# Decisões Arquiteturais — Goodies (ADRs condensados)

> Estas decisões NÃO são negociáveis durante a implementação.
> Se precisar mudar alguma, criar novo ADR em `docs/07_Decisoes.md` e discutir.

---

## ADR-001 — Stack (LOCKED)
FastAPI + Next.js 16 + Supabase (Postgres 15) + Redis (Upstash) + Fly.io + Vercel.
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
Asset ID L-BTC: `${LBTC_ASSET_ID}`
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
Decidido na faxina pré-m3 (2026-06-06). Ver `docs/11_Coerencia_Nubank_Portfolio_pre_m3.md`.
- **Aplicação E resgate de caixinha são `kind='investment'`** (o resgate volta positivo e neta o
  `total_invested`). Resgate de caixinha **nunca** é `income` — inflaria a taxa de poupança.
- Reclassificação de linhas curadas é **in-place/idempotente** (`api/scripts/reclassify_caixinhas.py`).
  **NÃO rodar `scripts/reset_ledger.py`** no banco curado — apagaria a curadoria. A migration
  `0009` cuida só das regras de import **futuro**.
- Caixinhas/CDB Nubank são ativos `asset_category='Renda Fixa'` (registro config-driven em
  `engines/portfolio/caixinhas.py`; **Reserva** já listada, `enabled=False` até criar). Valoração
  pós-fixada via `rf_cdi.py` com `settings.cdi_anual` (env `CDI_ANUAL`, provisório até o m5/BCB) —
  cobre o ADR-004 (`is_manual=true`, worker m3 não sobrescreve).
- **Santander = conta externa:** Pix do próprio nome vindos do Santander (~R$32k em `income/Extra`)
  contam como receita/despesa externa — **não** transferência interna (decisão reafirmada).

---

## Endereços de wallet (via `.env` — NÃO hardcodar)

> Valores reais ficam SÓ em `.env` (gitignored). Aqui e em todos os docs
> usamos apenas os nomes das variáveis. Ver `.claude/memory/security.md`.

| Rede | Variável de ambiente |
|---|---|
| ETH/ARB/HYPE | `${WALLET_EVM_ADDRESS}` |
| SOL | `${WALLET_SOL_ADDRESS}` |
| Liquid | `${WALLET_LIQUID_ADDRESS}` |

## TTLs de cache Redis

| Dado | TTL |
|---|---|
| B3 (BRAPI) | 4h — dias úteis apenas |
| Cripto (CoinGecko) | 2h |
| Tesouro Direto | 6h |
| Wallet scan | 4h |
| Benchmarks (CDI/IPCA/IBOV) | 24h |
| XIRR calculado | 1h (invalidar em nova operação) |

## Chave de nomes Redis

`{engine}:{type}:{identifier}`
Ex: `price:b3:PETR4`, `price:crypto:BTC`, `wallet:binance:spot`, `xirr:consolidated`
