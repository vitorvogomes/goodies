# SESSION m3-market-data — Prompt de inicialização

**Data de referência:** 2026-06-05
**Branch:** criar `m3-market` a partir de `main` (após mergear `m2-portfolio` → `main`)
**Milestone:** m3 — Market Engine (preços automáticos)
**Gate de saída (CLAUDE.md):** preços B3 e cripto atualizando automaticamente a cada
ciclo do worker **sem erro por 48h**; dashboard mostra valor de mercado atual sem entrada manual.

---

## Estado atual (o que já existe — NÃO refazer)

✅ **m2 Portfolio Engine 100% (17/17)**, gate validado (XIRR 15,25%, custo reconcilia 0,047%).
✅ Já existe scaffolding que o m3 vai **estender, não recriar**:
- Tabela **`asset_prices`** (`ticker` PK, `price_brl`, `price_usd`, `source`, `is_manual`,
  `fetched_at`) — migração `0008_asset_prices`. **Já é a tabela do m3.**
- Classe **`PriceCache`** em `api/engines/market/cache.py` (get/set/delete JSON + TTL,
  fail-soft; `check_redis` health). É a "interface de cache Redis" da STORY-03-01.
- **`service.fetch_prices(conn)`** e **`service.upsert_price(conn, ticker, price, source, is_manual)`**
  em `engines/portfolio/service.py` — o chokepoint de escrita de preço.
- Endpoint de preço manual: **`PUT /api/v1/portfolio/prices/{asset_symbol}`** (o épico
  fala em `POST /market/prices/{ticker}` — decidir se migra/duplica para `/market`).
- `.env` com **`BRAPI_TOKEN`** e **`COINGECKO_API_KEY`** (placeholders sincronizados em `.env.example`).
- Dev roda via **docker compose** (Postgres + Redis + API na porta 8000; dados em volume).

✅ Suite: **241 testes verdes**, mypy limpo (atualizado pela faxina pré-m3).

✅ **Faxina pré-m3 já feita (2026-06-06, ADR-011)** — ver `docs/11_Coerencia_Nubank_Portfolio_pre_m3.md`:
- Resgates de caixinha = `investment` net (não receita) → taxa de poupança real. `reclassify_caixinhas.py`
  (in-place). **NÃO rodar `reset_ledger`** no banco curado.
- Caixinhas (Snow Trip, Turbo) + CDB Guanabara são ativos `Renda Fixa` (`rf_cdi.py` + `caixinhas.py` +
  seeds; preço `is_manual`). `settings.cdi_anual` (env `CDI_ANUAL`) provisório → **o m5 troca pela
  série do BCB sem mexer no `rf_cdi`**. Patrimônio R$37,2k; XIRR consolidado 13,8%.
- Resolve o débito §3.12. O B0 abaixo (chokepoint `upsert_price`, precedência `is_manual`) já tem
  os preços RF `is_manual=true` (Flash, caixinhas, CDB) como caso de teste real.

---

## ⚠️ PRÉ-REQUISITOS EMBUTIDOS (do code-review do m2 — `docs/10_Debito_Tecnico_m2.md`)

**Resolver ANTES de plugar os fetchers** — senão o preço automático corrompe a carteira
silenciosamente. Estes itens viram as **primeiras stories do m3 (B0 — fundação)**:

1. **[§3.4] Chokepoint `upsert_price`** — mover a invalidação do cache XIRR para **dentro
   de `upsert_price`** (hoje está só no router do PUT manual; o worker m3 chamará `upsert_price`
   direto e deixaria o XIRR stale por até 1h). E definir a **regra de precedência `is_manual`**:
   o worker **não** sobrescreve um preço `is_manual=true` (Flash/RF/DeFi) que ele não tem fonte
   para cotar. Esse é o seam direto do Market Engine.

2. **[§3.2] Fonte única de categorias** — extrair as 6 categorias canônicas
   ("Ações Nacionais", "ETFs", "FIIs", "Renda Fixa", "Aposentadoria", "Cripto") para **um
   módulo de constantes** importado por `targets.py`, `b3_import.py`, `migration.py`,
   `service._IR_ALIQUOTAS` **e** pelos novos fetchers. Hoje a string está duplicada em 4
   lugares (e o Bridge doc usa casing errado) → uma divergência faz a posição sumir da
   alocação/IR sem erro.

3. **[§3.3] Categoria B3 robusta** — `b3_import._ACOES/_ETF/_FII` é allowlist hardcoded
   (ETF e FII terminam em 11 → fallback miscategoriza). Derivar a categoria das abas
   "Posição -" do relatório consolidado (que já separam Ações/ETF/Fundos/Tesouro). Crítico
   porque o worker m3 ingere qualquer ticker novo.

4. **[§2.1] XIRR com preço parcial** — `calculate_portfolio_xirr` inclui as compras de
   ativos **sem** preço sem o valor terminal → XIRR errado. Com preços automáticos
   intermitentes (e ativos recém-comprados sem cotação), isso passa a acontecer de verdade.
   Decidir a semântica (excluir do cashflow os ativos com posição aberta sem preço, ou usar
   custo como terminal) + teste de preço misto.

5. **[§3.1] Data de avaliação única** — hoje o XIRR usa `date.today()`, mas seeds/validador
   fixam datas. Threadar um conceito único de "data de avaliação" por service + worker +
   `validate_xirr.py`, senão o XIRR deriva e o gate não reproduz.

6. **[§3.5] Reconciliar arquitetura** — `docs/02_Arquitetura.md` descreve `queries.py`/
   `models.py`/view `positions` que **não existem**, e schema divergente. Reconciliar a doc
   com a realidade (ou refatorar) antes de empilhar o Market Engine. Respostas dos endpoints
   ainda são `dict[str, Any]` sem modelo Pydantic — considerar contrato tipado para o front.

> Itens menores (rastrear, não bloqueiam): §2.2 `refresh_token` no body do login, §2.3
> assert de `type` no token, §3.6 import do front bypassa o 401, §3.7 "primeiro usuário"
> hardcoded em 5 scripts (agora 7 — +2 seeds de caixinha), §3.8 DCA duplicado, §3.9 scripts sem
> teste / `b3_import` 76%, §3.10 Flash dias-corridos vs úteis, ~~§3.12 dados incompletos~~ →
> **resolvido (Guanabara/Caixinha); resta cripto (m4) + CDI real (m5)**.

---

## Escopo do m3 (EPIC-03) + sequência recomendada

Stories (PROGRESS.md `## Milestone m3`): 03-01 a 03-12. Sugestão de batches:

```
B0 (FUNDAÇÃO — pré-requisitos do code-review):
   §3.2 categorias SSOT  +  §3.4 upsert_price (cache + is_manual)  +  §3.1 data de avaliação
   §2.1 XIRR preço parcial  +  §3.3 categoria B3 robusta  +  §3.5 reconciliar doc
   ↓
B1: 03-02 Fetcher BRAPI (ações/ETF/FII, retry backoff, strip sufixo F)   [precisa BRAPI_TOKEN]
  + 03-03 Fetcher CoinGecko (mapa de IDs configurável, BRL/USD)          [precisa COINGECKO_API_KEY]
   ↓
B2: 03-04 Fetcher Tesouro Direto (matching flexível por nome)
  + 03-07 Fallback (Redis → Postgres asset_prices → manual, flag stale)
   ↓
B3: 03-05 Worker price_b3 (APScheduler, cron dias úteis 9-18h/4h)
  + 03-06 Worker price_crypto (cron 2h)   [NUNCA on-demand — só cron]
   ↓
B4: 03-09 Endpoints de leitura /market/prices  + 03-08 update manual
  + 03-10 Portfolio passa a usar preços do Market Engine (posições com valor real,
          respeitando precedência is_manual)
   ↓
B5: 03-11 Frontend — tela de preços + staleness  + 03-12 testes de integração (mock das APIs)
   ↓
GATE m3: preços B3+cripto atualizando via worker sem erro; validar 48h de estabilidade.
```

**Guardrails do CLAUDE.md (não violar):**
- Padrão de cache: chaves `{engine}:{type}:{identifier}` (`price:b3:PETR4`, `price:crypto:BTC`);
  TTL B3=4h, Cripto=2h, Tesouro=6h, Benchmark=24h.
- **Fallback:** Redis → Postgres (`asset_prices`) → manual → `{"value": null, "stale": true}`.
  **NUNCA HTTP 5xx por falha de API externa.**
- BRAPI: remover sufixo `F` (PETR4F → PETR4); retry 3× backoff (1s/2s/4s).
- CoinGecko: mapa de IDs em config (BTC=bitcoin, ETH=ethereum, …), não hardcoded; rate-limit → cache agressivo.
- **Cripto/Binance on-demand é proibido — cron only.** Binance/wallets é **m4**, não m3.
- APScheduler no mesmo processo FastAPI (não Celery).

---

## Credenciais / fontes de dados (me chame quando precisar)

| Fetcher | Credencial | Status |
|---|---|---|
| BRAPI (B3) | `BRAPI_TOKEN` | placeholder no `.env` — **confirmar valor real** |
| CoinGecko (cripto) | `COINGECKO_API_KEY` | placeholder no `.env` — **confirmar valor real** |
| Tesouro Direto | API pública (sem chave) | ok |
| BCB (CDI/IPCA — benchmarks) | API pública | é mais m5, mas a interface pode nascer aqui |

**Pedir ao Vitor os tokens reais (BRAPI/CoinGecko) antes do B1.** Sem eles, os fetchers
ficam só com testes mockados.

---

## Referências rápidas
- **Débito técnico (LER PRIMEIRO):** `docs/10_Debito_Tecnico_m2.md`
- **Arquitetura:** `docs/02_Arquitetura.md` §2.2 (fetchers), §6 (cache), §8 (APIs externas) —
  ⚠️ tem drift vs implementação (ver §3.5 do débito).
- **Stack/guardrails:** `CLAUDE.md` (padrão de cache, fallback, Liquid ADR-005).
- **Memória:** `.claude/memory/` (conventions, decisions, skills) + `MEMORY.md`
  (`m2-portfolio-gate` resume o estado e o débito).
- **Progresso:** `PROGRESS.md` (`## Milestone m3`).
- **Skills sugeridas:** `test-driven-development`, `systematic-debugging`,
  `supabase-postgres-best-practices` (queries de preço), `api-design-principles`.
  Lacunas sem skill (httpx fetchers, APScheduler, retry/backoff): seguir `decisions.md` + TDD.

---

## Perguntas para fazer ao usuário antes de começar
1. Mergear `m2-portfolio` → `main` agora e abrir `m3-market` a partir de `main`?
2. Fazer o **B0 (fundação / pré-requisitos do code-review) primeiro** (recomendado), ou
   ir direto aos fetchers e tratar o débito depois?
3. Tem os tokens reais de **BRAPI** e **CoinGecko** para colocar no `.env`?
4. O endpoint de preço migra para `/api/v1/market/*` (como no épico) ou mantém em
   `/api/v1/portfolio/prices`?

---

*Prompt pronto para colar em sessão nova:*

> Leia `CLAUDE.md`, `PROGRESS.md`, `docs/10_Debito_Tecnico_m2.md` e `SESSION_M3.md`.
> Vamos iniciar o **m3 — Market Engine**. **Antes dos fetchers**, implemente o **B0 (fundação)**
> com os pré-requisitos do code-review do m2 embutidos: (1) mover invalidação de cache para
> dentro de `upsert_price` + regra de precedência `is_manual`; (2) fonte única de categorias;
> (3) categoria B3 derivada das abas de Posição; (4) XIRR correto com preço parcial; (5) data
> de avaliação única; (6) reconciliar `docs/02_Arquitetura.md`. Depois siga os batches B1→B5
> do `SESSION_M3.md`. TDD sempre; cache/fallback do CLAUDE.md (nunca 5xx por API externa);
> Binance/wallets é m4. Me chame para os tokens BRAPI/CoinGecko. Atualize o PROGRESS.md ao
> concluir cada story.
