---
tipo: decisoes_adr
projeto: Goodies
autor: Minerva
data_inicio: 2026-06-02
tags: [goodies, adr, decisoes, arquitetura]
---

# Goodies — Architecture Decision Records (ADRs)

> Registro formal de decisões técnicas relevantes.
> Uma decisão aqui = não precisa ser re-discutida na implementação.

---

## ADR-001 — Stack principal

> **Emenda 2026-10-17:** Fly.io e Vercel removidos do projeto (workflow, `fly.toml`, `DEPLOY.md`).
> A v2.0 roda só em localhost; a infra de deploy será desenhada do zero na v2.1. As menções
> abaixo ficam como histórico.

**Data:** 2026-06-02  
**Status:** Aceito  
**Autor:** Minerva + Hatchepsut (Excalidraw)

### Contexto
Projeto pessoal, usuário único, orçamento ~R$ 30/mês. Precisa de: API REST, cálculos financeiros (XIRR, séries temporais), frontend reativo, banco relacional com auth, cache de preços, workers de background.

### Decisão
- **Backend:** FastAPI (Python) — ecosistema financeiro/científico maduro (scipy, numpy, pandas), async nativo, tipagem forte com Pydantic.
- **Frontend:** Next.js 14 (App Router) — SSR para SEO não é prioridade mas o App Router tem Server Components que simplificam fetch de dados.
- **Database:** Supabase (Postgres 15) — Postgres é padrão de fato para dados financeiros relacionais; Supabase adiciona auth JWT e RLS sem custo.
- **Cache:** Redis via Upstash — free tier suficiente para single-user com workers a cada 2-4h.
- **Backend deploy:** Fly.io Hobby — ~R$ 30/mês para 256MB RAM, mais que suficiente para carga de um usuário.
- **Frontend deploy:** Vercel Hobby — free para Next.js.

### Alternativas descartadas
- **Django:** mais verboso, ORM síncrono por padrão, overhead sem benefício para API pura.
- **Node.js (Express/Hono):** ecossistema científico/financeiro inferior para XIRR e análise de séries temporais.
- **Railway:** preço similar ao Fly.io mas menos controle.
- **PlanetScale:** MySQL sem suporte a UUID, sem RLS nativo.

### Consequências
- Cálculos XIRR e benchmarks ficam no backend (Python) — não no frontend.
- Workers de preço rodam no mesmo processo FastAPI via APScheduler (não Celery) para simplicidade.
- Decisão de stack é **locked** para o MVP — mudanças requerem novo ADR.

---

## ADR-002 — XIRR como métrica principal de retorno

**Data:** 2026-06-02  
**Status:** Aceito  
**Autor:** Hatchepsut (Brief)

### Contexto
A planilha atual usa `(resultado - aplicado) / aplicado` como "rentabilidade". Para portfólio DCA com aportes em momentos diferentes, essa métrica é metodologicamente incorreta — ignora o custo de oportunidade do timing.

### Decisão
XIRR (Extended Internal Rate of Return) é a métrica oficial de retorno do Goodies. Implementado via `scipy.optimize.brentq` sobre a série de cashflows (data, valor) de cada operação.

Regras de sinal:
- Compra → cashflow negativo (saída de caixa)
- Venda / rendimento → cashflow positivo (entrada de caixa)
- Posição atual → cashflow positivo na data de hoje (valor de mercado atual)

### Alternativas descartadas
- **TWR (Time-Weighted Return):** mais adequado para avaliação de gestores (elimina efeito de aportes), mas menos útil para o investidor individual que quer saber "o que meu dinheiro rendeu".
- **Retorno simples:** descartado — metodologicamente inválido para DCA.
- **MWR (Money-Weighted Return) manual:** XIRR *é* o MWR anualizado — não há diferença prática.

### Consequências
- Histórico completo de operações (data + valor) é obrigatório desde o primeiro aporte.
- Migração dos dados da planilha deve incluir todas as 400+ operações históricas com data exata.
- Testes de XIRR devem comparar resultado com Excel nos dados reais antes do deploy de m2.

---

## ADR-003 — APScheduler no mesmo processo FastAPI (não Celery)

**Data:** 2026-06-02  
**Status:** Aceito  
**Autor:** Minerva

### Contexto
Workers de background precisam: atualizar preços Redis a cada 2-4h, escanear wallets 3× ao dia, avaliar alertas diariamente. Para single-user com orçamento de ~R$ 30/mês.

### Decisão
APScheduler integrado ao ciclo de vida do FastAPI (`@app.on_event("startup")`). Roda no mesmo processo, sem Redis Broker, sem workers separados.

### Alternativas descartadas
- **Celery + Redis broker:** overhead de infraestrutura desnecessário para single-user. Celery precisa de um processo worker separado (= mais memória, mais complexidade de deploy).
- **Kubernetes CronJobs:** fora do escopo de custo.
- **Cloud Scheduler (GCP/AWS):** adiciona dependência de cloud externa.
- **Cron no sistema operacional do Fly.io:** Fly.io não expõe cron nativo de forma simples.

### Consequências
- Se a instância Fly.io reiniciar, os workers recomeçam automaticamente no startup.
- Se a instância ficar down (< 0,1% para Fly.io Hobby), preços ficam desatualizados até o próximo ciclo — aceitável para single-user.
- Workers devem ser idempotentes — rodar 2× o mesmo ciclo não deve duplicar dados.

---

## ADR-004 — Dados manuais como fallback, nunca bloqueantes

**Data:** 2026-06-02  
**Status:** Aceito  
**Autor:** Hatchepsut (Brief) + Minerva

### Contexto
Flash Debênture (R$ 13.207 = maior ativo da carteira), CDB Guanabara e posições DeFi não têm API pública. Sem esses dados, o portfólio total fica incompleto.

### Decisão
Ativos sem API aceitam **entrada manual via UI** com timestamp. O sistema exibe o último valor manual com indicador de data de atualização (`"Última atualização: 3 dias atrás"`). Nunca bloqueia carregamento por falta de dado manual.

Comportamento em cascata:
1. API externa disponível → usar preço da API
2. API fora / rate limit → usar cache Redis (com flag `stale: true`)
3. Cache expirado → usar `asset_prices` do Postgres (último salvo)
4. Nenhum dado disponível → exibir valor manual mais recente + timestamp
5. Nenhum dado nunca inserido → exibir `---` sem erro

### Consequências
- Campo `is_manual` + `fetched_at` em `asset_prices` para distinguir fonte.
- UI deve comunicar claramente quando um valor está desatualizado.
- Flash Debênture: Vitor atualiza manualmente ~1× por mês (rendimento acumulado visível na planilha).

---

## ADR-005 — Liquid Network: client dedicado

**Data:** 2026-06-02  
**Status:** Aceito  
**Autor:** Minerva

### Contexto
Vitor tem L-BTC em GenesisP2P (Liquid Network). A API do Liquid é `blockstream.info/liquid` — diferente do mainchain Bitcoin (`blockstream.info/btc`). Confusão entre os dois produz dados errados silenciosamente.

### Decisão
Implementar `fetchers/wallets/liquid.py` como cliente dedicado, sem reutilizar nenhuma lógica do fetcher de Bitcoin mainchain. Endpoint base: `https://blockstream.info/liquid/api/`.

### Consequências
- Endereço Liquid (`${WALLET_SIDESWAP_ADDRESS}` — wallet SideSwap; renomeado de `WALLET_LIQUID_ADDRESS` no m4) é validado como endereço Liquid, não Bitcoin.
- Liquid é **multi-asset**: o fetcher lê L-BTC (`${LBTC_ASSET_ID}`) **e** L-USDT (`${LUSDT_ASSET_ID}`) do mesmo endereço. L-BTC = 1:1 BTC, L-USDT = 1:1 USDt (via CoinGecko).
- O endereço SideSwap é **confidencial** (blinded): o esplora público devolve 0 UTXOs → **entrada manual** (`is_manual`, ver ADR-013).

---

## ADR-006 — Auth JWT customizado (sem Supabase Auth para login)

**Data:** 2026-06-02  
**Status:** Aceito  
**Autor:** Minerva

### Contexto
Supabase Auth suporta login por email/senha. Para single-user, é possível usar Supabase Auth diretamente ou implementar JWT simples no FastAPI.

### Decisão
JWT gerado e validado no FastAPI (`python-jose`). Supabase Auth NÃO é usado para autenticação de usuário — apenas para a conexão de banco (connection string). Motivo: evita round-trip ao Supabase para cada request autenticado; o FastAPI valida o JWT localmente.

Dois tipos de token:
- **User token:** emitido no login, scope `user`, expira em 15min (refresh token: 30 dias)
- **Hermes service token:** token de longa duração (90 dias), scope `hermes`, acesso limitado a `/hermes/*`

### Consequências
- Senha de usuário armazenada no Postgres (tabela `users`) com bcrypt hash.
- Single user = single account — sem cadastro público.
- `refresh_token` armazenado em httpOnly cookie (não em localStorage).

---

## ADR-007 — Hermes: braço operacional opcional, não bloqueante

**Data:** 2026-06-02  
**Status:** Aceito  
**Autor:** Hatchepsut (Brief)

### Contexto
O Hermes (agente Discord) tem `coleta_carteira.py` funcional e poderá consumir a API do Goodies. O risco é criar acoplamento onde o Goodies depende do Hermes para funcionar.

### Decisão
O Goodies funciona 100% sem o Hermes. O Hermes consome endpoints dedicados (`/hermes/*`) como cliente de leitura/escrita. Os endpoints Hermes são idempotentes — `POST /hermes/expenses` com os mesmos dados 2× não duplica transação (idempotency key via `X-Idempotency-Key` header).

### Consequências
- Endpoints `/hermes/*` têm auth de service token (não user token) — Hermes não faz login.
- O `coleta_carteira.py` existente pode coexistir com o Goodies durante desenvolvimento — não há conflito.
- Futuro: Hermes pode consultar `GET /hermes/resumo-geral` para briefing diário automatizado.

---

## ADR-008 — XIRR implementado em Python, não no banco

**Data:** 2026-06-02  
**Status:** Aceito  
**Autor:** Minerva

### Contexto
XIRR pode ser implementado como função SQL (via PL/pgSQL ou extensão) ou em Python. Postgres não tem XIRR nativo.

### Decisão
XIRR é calculado em Python (engines/portfolio/xirr.py) com scipy. O banco armazena as operações brutas; o backend calcula XIRR on-demand e faz cache do resultado.

Cache de XIRR: Redis com TTL de 1h (não precisa ser recalculado a cada request — só muda quando nova operação é inserida). Invalidar cache ao inserir operação.

### Consequências
- XIRR não está disponível como query SQL — precisa passar pelo backend.
- Cache garante que cálculos custosos não impactam latência do dashboard.
- Biblioteca `scipy` (e `numpy`) são dependências obrigatórias do backend.

---

## ADR-009 — Frontend: Next.js 16 / React 19 / Tailwind v4 (atualiza ADR-001)

**Data:** 2026-06-03  
**Status:** Aceito  
**Autor:** Vitor + Claude Code

### Contexto
ADR-001 fixou "Next.js 14" (versão atual em 2023). Em 2026, `create-next-app@latest` gera **Next.js 16 / React 19 / Tailwind v4**, e o Next 14 está sem suporte ativo.

### Decisão
Adotar **Next.js 16 (App Router) + React 19 + Tailwind v4** no `web/`. Substitui a cláusula "Next.js 14" do ADR-001 — os demais itens de stack permanecem inalterados.

Implicações técnicas:
- **Tailwind v4 é CSS-first:** tema via `@theme` em `app/globals.css` (não há `tailwind.config.ts`).
- **Middleware → `proxy.ts`:** o arquivo `middleware.ts` foi renomeado para `proxy.ts` no Next 16 (relevante para a proteção de rota da STORY-00-07).
- **React Compiler** habilitado (`reactCompiler: true` em `next.config.ts`).

### Consequências
- STORY-00-06 / STORY-00-07 e o EPIC-07 seguem as convenções do Next 16 (não 14).
- Skills `next-best-practices` / `frontend-design` aplicam padrões v16 (RSC, async APIs, `proxy.ts`).

---

## ADR-010 — Backend: gestão de dependências com uv (pyproject + uv.lock)

**Data:** 2026-06-03  
**Status:** Aceito  
**Autor:** Vitor + Claude Code

### Contexto
A STORY-00-02 criou `requirements.txt` (runtime, pip freeze) + `requirements-dev.txt`, **além** do `pyproject.toml` — que já declarava `[project.dependencies]` e o grupo dev. A lista de dependências ficava em duas fontes mantidas à mão, sujeitas a divergir; o `pyproject` servia só como metadado + config de ferramentas.

### Decisão
Adotar **[uv](https://docs.astral.sh/uv/)** como gerenciador de dependências do backend (`api/`):
- `pyproject.toml` é a **fonte única** das deps — runtime em `[project.dependencies]`, ferramentas em `[dependency-groups].dev` (PEP 735).
- `uv.lock` (commitado) fixa as versões exatas — a reprodutibilidade que o `requirements.txt` dava.
- `[tool.uv] package = false`: a app roda a partir do código-fonte (`pythonpath="."`); uv gerencia só a venv (`api/.venv`) + deps, sem buildar/instalar wheel (removidos `[build-system]`/hatchling).
- `requirements.txt` e `requirements-dev.txt` **removidos**.

Comandos: `uv sync` (base+dev), `uv sync --no-dev` (só runtime, imagem), `uv run <cmd>` (pytest/ruff/mypy/uvicorn/alembic). uv também provê o Python 3.12.

### Consequências
- **Dockerfile** copia o binário `uv` da imagem oficial e roda `uv sync --frozen --no-dev` numa venv em `/opt/venv` (fora de `/app`, p/ não ser sombreada pelo bind mount do compose).
- **CI** (`deploy.yml`) usa `astral-sh/setup-uv` + `uv sync --frozen` + `uv run ...` (dispensa `setup-python`).
- **pre-commit** roda ruff via `uv run --project api ruff`.
- Docs (`README`, `docs/LOCAL_DEV.md`, `docs/v1/03_Stack.md`) atualizados. Substitui a cláusula da STORY-00-02 sobre `requirements*.txt`; o restante da stack (ADR-001) é inalterado — uv é tooling, não troca de framework.

---

## ADR-011 — Caixinha/RDB Nubank = investment net (não receita); Santander externo

**Data:** 2026-06-06  
**Status:** Substituído em parte pelo ADR-015 (2026-10-17) — resgate passa a ser receita. Seguem valendo: caixinhas/CDB
como ativos RF, reclassificação in-place/idempotente, NÃO rodar `reset_ledger.py`, Santander externo.

### Contexto
A planilha tratava resgates de caixinha Nubank como receita, inflando a taxa de poupança; CDB/caixinhas não apareciam no portfólio; Pix do próprio nome via Santander pareciam transferência interna.

### Decisão
- **Aplicação E resgate de caixinha são `kind='investment'`** (o resgate volta positivo e neta o `total_invested`) — nunca `income`.
- Caixinhas/CDB Nubank viram ativos `asset_category='Renda Fixa'` (registro config-driven em `engines/portfolio/caixinhas.py`), valorados por `rf_cdi.py` com `settings.cdi_anual` (provisório até m5/BCB; `is_manual=true`, worker não sobrescreve — ADR-004).
- **Santander = conta externa:** `income/Extra` do Santander conta como receita externa, não transferência interna.

### Consequências
- Reclassificação de linhas curadas é **in-place/idempotente** (`api/scripts/oneoff/reclassify_caixinhas.py`); a migration `0009` cobre só o import futuro. **NÃO rodar `api/scripts/oneoff/reset_ledger.py`** no banco curado. Ver `docs/v1/11_Coerencia_Nubank_Portfolio_pre_m3.md`.

---

## ADR-012 — Market Engine (m3): endpoints, precedência de preço, fontes free-tier

**Data:** 2026-06-06  
**Status:** Aceito (m3)

### Contexto
O m3 automatizou preços (BRAPI/CoinGecko/Tesouro) com workers APScheduler, reusando `asset_prices` do m2 e respeitando preços manuais (Flash/RF/DeFi sem fonte de mercado).

### Decisão
- **Preços sob `/api/v1/market/*`** (contrato Pydantic `PriceOut`); o antigo `PUT /portfolio/prices` foi **removido**.
- **`portfolio.service.upsert_price` é o chokepoint único de escrita**, com precedência **`is_manual`** (worker nunca sobrescreve manual) e invalidação do cache de XIRR (ADR-008) + cache Redis de preço dentro do fluxo. `is_manual=true` ⇒ nunca `stale`.
- **Free-tier (cadência diária B3/Tesouro):** BRAPI grátis = 1.000 req/mês (1 ativo/req) → `price_b3` 1×/dia útil 19h; **Tesouro via Tesouro Transparente CSV** (open data, sem WAF). `ttl_b3=ttl_tesouro=26h`.

### Consequências
- `EVALUATION_DATE` única threada por service + seeds + validador. **Cripto/Binance só via cron (m4).** Ver `docs/v1/12_Gate_M3_Market.md`.

---

## ADR-013 — Wallet scan (m4): fontes, `source` p/ sweep, valoração manual/DeFi

**Data:** 2026-06-07  
**Status:** Aceito (m4)

### Contexto
O m4 escaneia carteiras cripto on-chain + Binance (6 fetchers) gravando `wallet_positions`, reusando o preço do m3 e tratando o que não é escaneável (Liquid confidencial, posições DeFi com vencimento).

### Decisão
- **6 fetchers fail-soft** (Etherscan ETH/ARB/PENDLE, Hyperliquid, Solana, Liquid, Bitcoin, Binance); sem credencial = no-op. **HYPE em 2 fontes** no mesmo endereço Rabby: L1 spot (Info API) + **HyperEVM nativo** (`eth_getBalance`, `HYPEREVM_RPC_URL`). HyperEVM em escopo **só p/ o HYPE nativo**.
- **O `source` (por fonte) controla o sweep** (snapshot-replace por source): cada (sub)fonte usa um `source` próprio — `hyperliquid` (spot) ≠ `hyperevm` — para que a queda de uma não varra o snapshot bom da outra (outage ≠ posição fechada).
- **Posições manuais** (`is_manual=true`, p/ Liquid confidencial): o sweep nunca as apaga e elas nunca ficam `stale`; editáveis inline na UI (upsert).
- **Valoração manual/DeFi** reusa o preço do m3 via aliases em `coingecko_ids` (chave UPPER). **Id da API CoinGecko ≠ slug do site** (`susdai`, não `staked-usdai`); YT-xSOL fica sem fonte (decisão).
- **Reconciliação é só cripto** (`reconcile` filtra `asset_operations` por `CRYPTO_CATEGORIES`); B3 e caixinhas Nubank vêm por outra via.

### Consequências
- Débito conhecido (ver `docs/15_Debito_Tecnico.md`): aliases DeFi carregam sufixo de vencimento; manual+escaneado do mesmo ativo pode contar dobrado; valoração de wallet/DeFi ignora a camada de cache do m3.

---

## ADR-014 — v2.0 só em localhost (sem deploy, sem CI)

**Data:** 2026-10-17  
**Status:** Aceito (v2.0)

### Decisão
Fly.io, Vercel e GitHub Actions removidos (commit d3748a4). A v2.0 roda só local (`docker compose` com postgres 15,
redis 7 e api + `pnpm dev`); nenhum host de nuvem recebe dado financeiro. Backup local diário (`pg_dump`, fora do
repo). Infra de deploy desenhada do zero na v2.1.

### Consequências
Supabase, Upstash, Fly e Vercel não são usados; `DATABASE_URL`/`REDIS_URL` só apontam para localhost ou o compose.
`git push` é manual. Ver spine AD-18.

---

## ADR-015 — Resgate é receita (substitui o ADR-011 nesse ponto)

**Data:** 2026-10-17  
**Status:** Aceito (PRD v2)

### Decisão
Resgate de caixinha/RF/corretora é receita, exibido em linha própria e reclassificado em todo o histórico (FR-19,
migração idempotente). A taxa de poupança usa a **receita do trabalho** (sem resgates), então o gate
jun/2026 = 55,48% continua válido.

### Consequências
O ADR-011 fica substituído nesse ponto. Ver spine AD-6/AD-7/AD-16.

---

## ADR-016 — Base completa até 16/10/2026 e gate de dados pela própria base

**Data:** 2026-10-18  
**Status:** Aceito (v2.0, Épico 2)

### Decisão
Arquivos de `files/` importados (Nubank PF/MEI até 16/10/2026, movimentação B3 jun–out/2026 sem a liquidação D+2
duplicada, integralizações Flash, consolidado B3 de set/2026, caixinha Nu Reserva Imediata). Transações importadas
desde 2026-10-18T06:07Z ficam pendentes de revisão (categoria sugerida pelo histórico, nunca `manual`).

### Consequências
Os 55,48% da planilha não são reproduzíveis pela base; o invariante das revisões de dado é a taxa de poupança de
cada mês igual à do baseline fixado (jun/2026 = 57,46% na v1; desde a Story 2.6, 56,87% na fórmula v2 fixada em
`pinned_savings_v2.txt`), salvo deltas esperados listados. Ver
`.claude/memory/decisions.md`.

---

*→ [[02_Arquitetura]]*
*→ [[01_PRD]]*
*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*
