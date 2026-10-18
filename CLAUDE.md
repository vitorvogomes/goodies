# Goodies — CLAUDE.md

Plataforma pessoal de controle financeiro. Usuário único: Vitor.
Referências completas: `docs/project-context.md` | backlog v2: `docs/v2/planning/epics.md` (v1 em `docs/v1/`)

---

## Memória do projeto (ler no início de cada sessão)

- **Convenções de código:** `.claude/memory/conventions.md`
- **Decisões arquiteturais (ADRs):** `.claude/memory/decisions.md` — não violar
- **Segurança / segredos:** `.claude/memory/security.md` — `.env` + `.env.example` sincronizados, gitleaks, nada de segredo no chat
- **Skills e quando usar:** `.claude/memory/skills.md`

---

## Workflow de sessão

### Iniciar
1. `/status` → identificar próxima story pendente no `PROGRESS.md`
2. `/story N.M` → carregar a story de `docs/v2/planning/epics.md` + confirmar o que será implementado

### Implementar (TDD obrigatório)
3. **RED** — escrever teste que falha: `pytest tests/... -v -k "test_novo"`
4. **GREEN** — implementar o mínimo para passar
5. **REFACTOR** — limpar sem quebrar os testes
6. Repetir até todos os critérios de aceite da story verificados

### Encerrar story
7. `/test` → cobertura ≥ 80% nas engines críticas
8. `/code-review` → `/done N.M` → atualiza `PROGRESS.md` + commit local (push é manual)

### Verificar milestone
9. `/gate m1..m4` → antes de avançar para o próximo marco da v2

---

## Skills — ativação e guardrails

Roteamento autoritativo em `.claude/memory/skills.md` (área→skill + matriz milestone→skills).
`/story` lê o `skills:` da story (ou deriva da matriz) e **invoca** as skills certas.

**Guardrail crítico — `supabase`:** o banco é Postgres 15 local (compose); não há Supabase na v2.0.
Para SQL use `supabase-postgres-best-practices` (só o conteúdo Postgres). **Nunca** use skills de Supabase para
auth/JWT/login (é JWT custom no FastAPI — ADR-006), supabase-js/RLS/Edge Functions ou migrations (são **Alembic**).

Lacunas sem skill (Redis cache, worker APScheduler, fetcher httpx, scipy/XIRR, CI/CD):
seguir `decisions.md` + `conventions.md` + TDD/`systematic-debugging`.

---

## Stack (não mudar sem ADR) — só localhost (ADR-014)

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI 0.136 / Python 3.12 — `api/` (monólito modular, engines em camadas — spine AD-1/AD-2) |
| Frontend | Next.js 16 App Router / React 19 / TypeScript — `web/` (ADR-009), shadcn/ui radix new-york |
| Database | PostgreSQL 15 no `docker compose`, asyncpg direto (sem ORM), migrações Alembic |
| Cache | Redis 7 no `docker compose` (`redis[asyncio]`, `common.cache`) |
| Scheduler | APScheduler no mesmo processo FastAPI (não Celery) |
| Ambiente | `docker compose up` (postgres, redis, api) + `cd web && pnpm dev`. Sem deploy, sem CI, sem nuvem: Supabase, Upstash, Fly e Vercel não são usados. Infra de deploy do zero na v2.1 |
| Backup | `pg_dump` diário + antes de toda migração, em `BACKUP_DIR` (fora do repo) — runbook em `docs/LOCAL_DEV.md` |

Versões travadas e invariantes: `docs/v2/planning/architecture/architecture-goodies-2026-10-17/ARCHITECTURE-SPINE.md`.

## Auth — CRÍTICO

**NÃO usar Supabase Auth para login.** (ADR-006)
JWT customizado no FastAPI com `python-jose` + `passlib[bcrypt]`.
Refresh token em httpOnly cookie. Access token em memória React (não localStorage).

---

## XIRR — métrica principal de retorno

```python
# api/engines/portfolio/xirr.py — NÃO usar (resultado-aplicado)/aplicado
from scipy.optimize import brentq

def xirr(cashflows: list[tuple[date, float]]) -> float:
    # Compras: valor negativo. Vendas/posição atual: positivo.
    dates, amounts = zip(*sorted(cashflows, key=lambda x: x[0]))
    days = [(d - dates[0]).days for d in dates]
    npv = lambda r: sum(a / (1+r)**(d/365) for a, d in zip(amounts, days))
    return brentq(npv, -0.999, 100.0, xtol=1e-8)
```

Regressão: XIRR consolidado, por classe e por ativo = baseline da Story 1.3 (`EVALUATION_DATE` fixa, preços congelados).

---

## Liquid Network (ADR-005)

```python
import os
LIQUID_BASE_URL = os.environ["LIQUID_BASE_URL"]   # https://blockstream.info/liquid/api — NÃO /btc/api
LBTC_ASSET_ID   = os.environ["LBTC_ASSET_ID"]     # constante pública L-BTC — valor em .env (ADR-005)
LUSDT_ASSET_ID  = os.environ["LUSDT_ASSET_ID"]    # constante pública L-USDT (Liquid é multi-asset)
```
Client dedicado em `api/engines/market/fetchers/wallets/liquid.py` (multi-asset: L-BTC + L-USDT).
Proibido reutilizar fetcher Bitcoin mainchain. Endereço SideSwap é confidencial → entrada manual.

---

## Padrão de cache Redis

```
Keys: {engine}:{type}:{identifier}  →  price:b3:PETR4 | price:crypto:BTC | xirr:consolidated
TTLs: B3=26h | Cripto=2h | Tesouro=26h | Wallet=14h | Benchmark=24h | XIRR=1h
      (B3/Tesouro = cadência DIÁRIA por causa do free-tier: BRAPI grátis 1.000 req/mês [1
       ativo/req, sem batch] → price_b3 1×/dia útil 19h BRT; Tesouro publica 1×/dia útil.
       Preço manual: is_manual=true → nunca expira/stale; worker não sobrescreve. ADR-012.)
Fallback: Redis → Postgres (asset_prices) → manual → {"value": null, "stale": true}
NUNCA retornar HTTP 5xx por falha de API externa.
```

---

## Gates de qualidade da v2.0 (marcos do PRD §6.1)

Todos os marcos exigem: suíte verde com cobertura ≥ 80%, `pnpm test/lint/build`, `GET /api/v1/health` → 200 com
postgres+redis, banco em `head` e **nenhum teste `dados_reais` pulado**. Gate de dados permanente:
**taxa de poupança de cada mês = a do baseline fixado** (jun/2026 = 57,46% com a base completa; os 55,48% da
planilha não são reproduzíveis — ADR-016). A receita do trabalho não inclui resgates (ADR-015).

| Marco | Épicos | Gate (`/gate mK`) |
|---|---|---|
| m1 — Ritual confiável | 1–5 | poupança por mês = baseline (ADR-016), contagens, zero órfãs, deltas esperados, XIRR = baseline da Story 1.3; UJ-1 (importar → revisar → saldo PF conferido) e UJ-5 (Assistente de recuperação); jul/2024–mai/2026 fechados em bloco |
| m2 — Caixa e orçamento | 6 | golden do orçamento (consumido R$ 6.912,37; disponível R$ 8.405,59; financiado R$ 2.994,77); deltas dos meses com Repasse; SM-1 parcial registrada |
| m3 — Investimentos e aportes | 7–8 | XIRR consolidado = baseline (salvo correção explicada); conciliação B3/carteiras nas tolerâncias da AD-13; distribuição fecha ao centavo (2.200 = 1.700 + 500); SM-1 registrada |
| m4 — Histórico e ajustes | 9–10 | `metricas`: SM-1 ≥ 30 dias, SM-2/SM-3/SM-5 na meta; nenhuma rota v1 sem substituto; "no raw color" sem exceções |

Decisões que valem para todos os gates: ADR-014 (v2.0 só em localhost, sem deploy nem CI) e ADR-015 (resgate é
receita, em linha própria; o ADR-011 foi substituído nesse ponto). Detalhe por marco em `PROGRESS.md`.

## NÃO fazer

- ❌ Retorno como `(resultado-aplicado)/aplicado` — use XIRR
- ❌ Reutilizar fetcher Bitcoin para Liquid Network
- ❌ Chamar Binance API on-demand — cron only
- ❌ `access_token` em localStorage
- ❌ HTTP 5xx por falha de API externa
- ❌ Supabase Auth para login (ADR-006) — e nenhum serviço de nuvem (ADR-014)
- ❌ `git push` (o Vitor faz manual) e `docker compose down -v` (apaga o banco real)
- ❌ Migrar o banco sem backup feito antes
- ❌ Celery — APScheduler é suficiente
- ❌ Commitar `.env` com valores reais
- ❌ Misturar rendimentos de FII com ganho de capital em `asset_operations`
- ❌ Seguir padrões Flash Capital se conflitarem com este CLAUDE.md
