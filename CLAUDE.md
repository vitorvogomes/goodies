# Goodies — CLAUDE.md

Plataforma pessoal de controle financeiro. Usuário único: Vitor.
Referências completas: `docs/project-context.md` | `docs/` (épicos + stories)

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
2. `/story XX-YY` → carregar story + confirmar o que será implementado

### Implementar (TDD obrigatório)
3. **RED** — escrever teste que falha: `pytest tests/... -v -k "test_novo"`
4. **GREEN** — implementar o mínimo para passar
5. **REFACTOR** — limpar sem quebrar os testes
6. Repetir até todos os critérios de aceite da story verificados

### Encerrar story
7. `/test` → cobertura ≥ 80% nas engines críticas
8. `/done XX-YY` → atualiza `PROGRESS.md` + commit

### Verificar milestone
9. `/gate mX` → antes de avançar para o próximo milestone

---

## Stack (não mudar sem ADR)

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI 0.111+ / Python 3.12 — `api/` |
| Frontend | Next.js 14 App Router / TypeScript — `web/` |
| Database | Supabase (Postgres 15) via asyncpg direto (sem ORM) |
| Cache | Redis via Upstash (`redis[asyncio]`) |
| Scheduler | APScheduler no mesmo processo FastAPI (não Celery) |
| Deploy | Fly.io (API) + Vercel (web) |

---

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

Gate m2: XIRR Python == Excel XIRR (±0,1 pp) nos dados históricos.

---

## Liquid Network (ADR-005)

```python
import os
LIQUID_BASE_URL = os.environ["LIQUID_BASE_URL"]   # https://blockstream.info/liquid/api — NÃO /btc/api
LBTC_ASSET_ID   = os.environ["LBTC_ASSET_ID"]     # constante pública L-BTC — valor em .env (ADR-005)
```
Client dedicado em `api/engines/market/fetchers/wallets/liquid.py`.
Proibido reutilizar fetcher Bitcoin mainchain.

---

## Padrão de cache Redis

```
Keys: {engine}:{type}:{identifier}  →  price:b3:PETR4 | price:crypto:BTC | xirr:consolidated
TTLs: B3=4h | Cripto=2h | Tesouro=6h | Wallet=4h | Benchmark=24h | XIRR=1h
Fallback: Redis → Postgres (asset_prices) → manual → {"value": null, "stale": true}
NUNCA retornar HTTP 5xx por falha de API externa.
```

---

## Gates de qualidade por milestone

| Milestone | Gate |
|---|---|
| m0 | `GET /api/v1/health` → 200 com postgres+redis. Deploy funcionando. |
| m1 | taxa de poupança junho/2026 == planilha (±0,1%) |
| m2 | XIRR Python == Excel XIRR (±0,1 pp) |
| m3 | Preços atualizando sem erro por 48h |
| m4 | Posições cripto escaneadas sem entrada manual |
| m5 | CDI/IPCA/IBOV no dashboard. Alerta concentração Flash ativo. |
| m6 | Falha de worker notifica Discord <5min |
| m7 | 30 dias de uso sem abrir a planilha |

---

## NÃO fazer

- ❌ Retorno como `(resultado-aplicado)/aplicado` — use XIRR
- ❌ Reutilizar fetcher Bitcoin para Liquid Network
- ❌ Chamar Binance API on-demand — cron only
- ❌ `access_token` em localStorage
- ❌ HTTP 5xx por falha de API externa
- ❌ Supabase Auth para login (ADR-006)
- ❌ Celery — APScheduler é suficiente
- ❌ Commitar `.env` com valores reais
- ❌ Misturar rendimentos de FII com ganho de capital em `asset_operations`
- ❌ Seguir padrões Flash Capital se conflitarem com este CLAUDE.md
