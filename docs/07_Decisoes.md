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
> Na v2, os invariantes de arquitetura (AD-1..AD-19) estão no
> [ARCHITECTURE-SPINE](v2/planning/architecture/architecture-goodies-2026-10-17/ARCHITECTURE-SPINE.md); onde um ADR
> abaixo descreve a v1, a nota **Na v2** diz o que vale hoje.

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
- Liquid é **multi-asset**: o fetcher lê L-BTC (`settings.lbtc_asset_id`) **e** L-USDT (`settings.lusdt_asset_id`, constantes públicas em `api/config.py` desde 10/11/2026) do mesmo endereço. L-BTC = 1:1 BTC, L-USDT = 1:1 USDt (via CoinGecko).
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
- **Na v2:** as operações das caixinhas vêm das transações (Story 7.5; a escolha manual em `transaction_caixinha`
  vence) e o valor é `portfolio/rf.cdi_value` sobre o CDI diário publicado (`benchmark_data`, Story 7.4), com os saldos
  informados em Ajustes › Preços manuais como âncora (`rf_balance_anchors`, 0047). A constante `cdi_anual` saiu.
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
- **`market.service.upsert_price` é o chokepoint único de escrita** (na v1 ficava em `portfolio.service`), com precedência **`is_manual`** (worker nunca sobrescreve manual) e invalidação do cache de XIRR (ADR-008) + cache Redis de preço dentro do fluxo. `is_manual=true` ⇒ nunca `stale`.
- **Free-tier (cadência diária B3/Tesouro):** BRAPI grátis = 1 ativo/req (1.000 req/mês na época; 15.000 e 3 meses de histórico em 11/2026) → `price_b3` 1×/dia útil 19h; **Tesouro via Tesouro Transparente CSV** (open data, sem WAF). `ttl_b3=ttl_tesouro=26h`.

### Consequências
- `EVALUATION_DATE` única threada por service + seeds + validador. **Cripto/Binance só via cron (m4).** Ver `docs/v1/12_Gate_M3_Market.md`.
- **Na v2:** o token cripto sem cotação tem preço manual em US$ (`source='manual_usd'`); o R$ segue a cotação do dólar
  (USDT/USDC) a cada `price_crypto`, e o histórico guarda cada dia na cotação do dia.

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
- **Na v2:** Investimentos › Conciliação confere o consolidado B3 (quantidade e valor por ativo, com as notas
  explicadas de bonificação e direito de subscrição) e as carteiras (Story 7.9). Nos trilhos do Nubank, só a corretora
  (B3) guarda caixa esperando virar ativo (`transit.Rail.holds_cash`); Tesouro, RF Nubank e Flash mostram o resíduo
  como diferença de conciliação.

### Consequências
- Débito conhecido na época (ver `docs/v1/15_Debito_Tecnico-v1.md`): aliases DeFi carregam sufixo de vencimento; manual+escaneado do mesmo ativo pode contar dobrado; valoração de wallet/DeFi ignora a camada de cache do m3.

---

## ADR-014 — v2.0 só em localhost (sem deploy, sem CI)

**Data:** 2026-10-17  
**Status:** Superado pelo ADR-018 (2026-11-10) — valeu para a v2.0

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
migração idempotente). A taxa de poupança usa a **receita do trabalho** (sem resgates). (O gate de 55,48% citado
aqui foi substituído pelo baseline por mês do ADR-016.)

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

## ADR-017 — Distribuição do aporte executável: lotes, troco e aportes fixos

**Data:** 2026-10-18  
**Status:** Aceito (pedido do Vitor, depois da v2.0)

### Decisão
- O sugerido de cada ativo é o que se compra de fato: B3 (ação, FII, ETF) em cotas inteiras e Tesouro em 0,01 título
  com a ordem mínima de R$ 30, ao preço de hoje, arredondado à cota mais próxima que cabe na classe
  (`planning/distribution.Lot`). Renda fixa, caixinhas e cripto seguem ao centavo.
- O troco das cotas segue a ordem: 1. reserva de emergência até encher; 2. caixinha Turbo até R$ 5 mil (o teto dos
  115% do CDI) — só quando a `caixinha:turbo` está ligada à reserva, e como a Turbo é parte da reserva esse passo
  pode levar a reserva além do alvo; 3. os objetivos do mais perto de ser concluído (maior % do alvo) ao mais longe.
  O travado é pulado e o troco segue ao próximo (reserva travada pula também a Turbo); depois, classes de valor
  livre; o resto fica sem destino ("fica para o próximo aporte").
- Aportes fixos do mês (`fixed_contributions`, revisão 0050): o valor que um objetivo ou ativo recebe todo mês (Flash
  R$ 1.000, caixinha Ana Maria R$ 4.000) é trava padrão da distribuição; a trava gravada no mês vence. Ativo fixo numa
  classe sem meta por ativo leva a classe ao valor fixo; numa classe com metas, a classe recebe ao menos os fixos dela;
  ativo fixo de um objetivo (caixinha) vira o fixo do objetivo.
- "O que falta aplicar" (lista de compras), por classe e dentro do que falta nela: primeiro os ativos de valor livre
  (o R$ que falta, reduzidos em proporção se passarem do que falta na classe); com o que sobra, os ativos de lote
  (cotas do plano − as que entraram no mês; travado ou fixo: o R$ que falta), em lotes inteiros.

### Consequências
A base do plano é o valor de hoje menos o que entrou no mês: o plano não muda a cada depósito, mas anda com o
mercado (valores e lotes ao preço de hoje). A lista de compras usa o que já entrou. Uma meta por ativo abaixo de
meia ordem mínima (no Tesouro, menos de R$ 15) nunca vira compra; de meia ordem para cima, vira a ordem mínima.

---

## ADR-018 — v2.1 na nuvem: Railway (substitui o ADR-014)

**Data:** 2026-11-10  
**Status:** Aceito (pedido do Vitor)

### Contexto
Rodando só em localhost, o controle financeiro só abria na máquina de casa. O Vitor quer acessá-lo de qualquer lugar
e já paga o Railway na conta da empresa, da qual é o único admin.

### Decisão
- O Goodies roda no **Railway**: um projeto, ambiente `production`, quatro serviços — Postgres **15** (imagem
  `ghcr.io/railwayapp-templates/postgres-ssl:15`, igual ao `pg_dump` 15 da imagem da api e ao ADR-001), Redis 7,
  `api` (root `api/`, `api/Dockerfile`) e `web` (root `web/`).
- **O web é a única porta pública** (subdomínio `*.up.railway.app`). O Next repassa `/api/v1/*` para a api pela rede
  privada (`API_INTERNAL_URL`); a api, o Postgres e o Redis não têm domínio público. Assim o cookie de refresh
  (`httpOnly`, `samesite=lax`, `secure` em produção) e o `proxy.ts` seguem na mesma origem (ADR-006 intacto).
- A api roda com **1 réplica e sem dormir** (APScheduler no processo — ADR-003).
- **Migração em produção pela subida da api** (`AUTO_MIGRATE=true`): backup antes, depois `alembic upgrade head`.
  Num banco vazio a subida faz o bootstrap: `0002_refresh_token_hash` → admin de `ADMIN_EMAIL`/`ADMIN_PASSWORD` → `head`
  (as sementes por usuário das migrações caem no admin). As duas variáveis só existem na 1ª subida.
- **Backups:** job `db_backup` diário + `restore_check` mensal num volume do Railway em `/backups`, e cópia fora do
  Railway por script local rodado à mão (`scripts/backup_railway.sh`).
- **Segredos de produção só nas variáveis do Railway**, gerados novos (não reaproveitar os do `.env` local) e nunca
  colados no chat. O `.env` local passa a ser só de desenvolvimento.
- O banco de produção **começa vazio**; o dump curado da máquina de casa é restaurado numa etapa posterior.
- `docker compose` + `pnpm dev` seguem como ambiente de **desenvolvimento**. Deploy = push manual no `main` (o
  Railway constrói a partir do GitHub); sem CI.

### Consequências
- Supabase, Upstash, Fly e Vercel continuam fora; a nuvem é só o Railway.
- O `scripts.ops.migrar` e o gate `dados_reais` dependem do backup fixado em `pinned_backup.txt`, que só existe na
  máquina de casa: até o dump chegar, ficam pendentes (os testes aparecem pulados). Antes de um push com migração,
  rodar a suíte local.
- `/docs` e `/openapi.json` ficam desligados em produção. Custo: quatro serviços sempre ligados.
- Em produção a subida da api recusa `DATABASE_URL`/`REDIS_URL` vazias ou em localhost: uma referência `${{…}}`
  que não resolve não cai mais em silêncio no padrão de dev (aconteceu duas vezes no 1º deploy).
- Ver `docs/DEPLOY_RAILWAY.md` (runbook) e spine AD-18.

## ADR-019 — v2.2: oportunidade nos aportes, histórico de preço, DeFi por saldo, pizza e celular

**Data:** 2026-11-11  
**Status:** Aceito (pedido do Vitor; plano aprovado)

**Contexto:** com a produção no ar, o Vitor pediu melhorias de uso diário: a variação de preço
influenciando a sugestão de aportes, cripto em R$ e US$ em todo lugar, DeFi sem preço manual, gráficos
de pizza, um Painel mais claro e o app usável no navegador do celular.

**Decisões:**
- **Oportunidade de mercado** (`portfolio.opportunity`): três sinais por ativo com cotação — variação em
  3 meses, preço × preço médio de compra, distância da máxima de 52 semanas —, no **1º dia do mês**
  (a divisão não muda a cada pregão; mês passado não é refeito com o mercado de hoje). Fator
  `1 + 0,25·s`, entre **0,75 e 1,25**, multiplica o peso do ativo **dentro da classe** (o déficit e a
  sobra); a divisão entre as classes, as travas, os aportes fixos e o "só o piso" não mudam. Ligado por
  mês em `month_plans.oportunidade` (0052), **desligado por padrão** — os goldens da distribuição seguem.
- **Histórico de preço** (`market.history_backfill`, job mensal `price_history`): um ano de preço diário
  dos ativos em carteira — **COTAHIST anual da B3** (o BRAPI grátis só dá 3 meses), CSV do Tesouro
  Transparente com todas as datas, CoinGecko `market_chart`. Só grava os dias que faltam; o parse do
  COTAHIST roda numa thread (não trava a api). Efeito colateral aceito: a valoração de um fim de mês
  **aberto** passa a usar o fechamento real daquele dia em vez do último dia em que o app abriu (meses
  fechados são snapshot e não mudam).
- **DeFi por saldo em US$** (`defi_balance_anchors`, 0051): o saldo que o protocolo mostra numa data,
  a quantidade de tokens dessa data e o APY opcional; o **preço por token** (saldo ÷ quantidade) rende
  por dia e vai ao chokepoint como manual em dólar (`source='defi_anchor'`). Só para token sem cotação de
  mercado (SOL/USDC recusam). Token que perde o saldo volta a `manual_usd` com o último preço.
- **Cripto em R$ e US$**: a conversão é da API (`common.money.to_usd`, AD-4); o web só formata
  (`formatUSD` pt-BR, "US$ 1.234,56").
- **Pizza** permitida (emenda o DESIGN.md): uma fatia por item, em tons do verde principal
  (`--pie-1..8`), sempre com legenda de nome, % e valor; as fatias e os % vêm da API
  (`common.shares`, somam 100,00). Nada de gráfico no Painel continua valendo.
- **Painel**: Saldo em caixa (conferido) no topo e Fluxo do mês (`planning.calc.flow_terms`) no lugar de
  "disponível × restante"; num mês fechado, o fluxo sai dos termos congelados. Nomes na tela: "Livre
  para gastos" (disponível) e "Sobra do mês" (restante); a conta não mudou.
- **Celular é alvo** (emenda EXPERIENCE/DESIGN): navegação inferior abaixo de 1024px, `DataTable` vira
  cartão abaixo de 640px (papéis `mobile`), tabelas cruas usam `table-stack` + `data-label`, seções
  longas recolhidas (`Section`).

**Consequências:** duas migrações (0051, 0052) entram pela subida com backup; o primeiro `price_history`
roda no catch-up depois do deploy (~1 min). A real do Painel usa o último IPCA publicado para o mês que
falta (`Valued.estimated`).
