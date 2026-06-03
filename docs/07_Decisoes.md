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
- Endereço Liquid (`${WALLET_LIQUID_ADDRESS}`) deve ser validado como endereço Liquid, não Bitcoin.
- L-BTC é convertido para BRL via `CoinGecko BTC/BRL` (L-BTC = 1:1 com BTC).

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

*→ [[02_Arquitetura]]*
*→ [[01_PRD]]*
*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*
