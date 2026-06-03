---
tipo: stack
projeto: Goodies
versao: "1.0"
autor: Minerva
data: 2026-06-02
status: aprovado
tags: [goodies, stack, tecnologia, infra]
---

# Goodies — Stack Técnico

> Decisão de stack está registrada em ADR-001 em `07_Decisoes.md`.
> Este documento detalha versões, libs principais e configurações críticas.

---

## Resumo

| Camada | Tecnologia | Versão alvo | Plano/Custo |
|---|---|---|---|
| Backend | FastAPI (Python) | 0.111+ | — |
| Frontend | Next.js | 14+ (App Router) | — |
| Database | Supabase (Postgres) | 15 | Free tier |
| Cache | Redis (Upstash) | — | Free tier |
| Backend deploy | Fly.io | — | Hobby ~R$30/mês |
| Frontend deploy | Vercel | — | Hobby free |
| Auth | Supabase Auth + JWT customizado | — | Free |
| CI/CD | GitHub Actions | — | Free |

---

## Backend — FastAPI (Python)

### Runtime
- Python **3.12**
- FastAPI **0.111+**
- Uvicorn (server ASGI)
- Pydantic v2 (validação de schemas)

### Dependências principais

```txt
# requirements.txt
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
pydantic>=2.7.0
pydantic-settings>=2.2.0        # config via env vars
asyncpg>=0.29.0                 # driver Postgres assíncrono
redis[asyncio]>=5.0.0           # cliente Redis (compatível Upstash)
httpx>=0.27.0                   # cliente HTTP assíncrono (fetchers de API)
scipy>=1.13.0                   # XIRR (scipy.optimize.brentq)
numpy>=1.26.0                   # arrays para cálculos financeiros
pandas>=2.2.0                   # manipulação de séries temporais
yfinance>=0.2.40                # IBOV benchmark
apscheduler>=3.10.0             # workers de preço (scheduler)
structlog>=24.0.0               # logs estruturados
sentry-sdk[fastapi]>=2.0.0      # error tracking
slowapi>=0.1.9                  # rate limiting
python-jose[cryptography]>=3.3.0 # JWT
passlib[bcrypt]>=1.7.4          # hash de senha
python-multipart>=0.0.9         # form data
```

### Configuração de ambiente (env vars)
```bash
# Database
DATABASE_URL="postgresql+asyncpg://..."   # Supabase connection string

# Redis
UPSTASH_REDIS_REST_URL="https://..."
UPSTASH_REDIS_REST_TOKEN="..."

# Auth
JWT_SECRET_KEY="..."                       # mínimo 32 chars, gerado com openssl rand
JWT_ALGORITHM="HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Hermes service token (escopo restrito)
HERMES_SERVICE_TOKEN="..."

# APIs externas
BRAPI_TOKEN="..."
COINGECKO_API_KEY=""                       # free tier sem key
BINANCE_API_KEY="..."
BINANCE_SECRET_KEY="..."
ETHERSCAN_API_KEY="..."
SOLSCAN_API_KEY=""                         # free tier

# Sentry
SENTRY_DSN="..."

# App
ENVIRONMENT="production"                   # "development" | "production"
CORS_ORIGINS="https://goodies.vercel.app"
```

### Dockerfile
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## Frontend — Next.js

### Runtime
- Node.js **20 LTS**
- Next.js **14** (App Router, Server Components)
- TypeScript **5.4+**
- React **18**

### Dependências principais

```json
{
  "dependencies": {
    "next": "14.x",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@tanstack/react-query": "^5.40.0",
    "recharts": "^2.12.0",
    "date-fns": "^3.6.0",
    "lucide-react": "^0.383.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.3.0",
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    "@radix-ui/react-toast": "^1.2.1"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "tailwindcss": "^3.4.0",
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "eslint": "^8.57.0",
    "eslint-config-next": "14.x"
  }
}
```

**Notas de UI:**
- Sem shadcn/ui instância local — usar Radix primitives diretamente (menos overhead)
- Recharts para todos os gráficos (área, linha, pizza para alocação)
- Tailwind com custom colors para o tema do Goodies
- Dark mode: sim, via `next-themes`

### Variáveis de ambiente
```bash
NEXT_PUBLIC_API_URL="https://goodies-api.fly.dev"
```

---

## Database — Supabase (Postgres 15)

### Setup
- Projeto: região `sa-east-1` (São Paulo)
- Extensions: `pg_stat_statements` (habilitada no painel)
- RLS: habilitado por segurança em profundidade (mesmo single-user)
- Backups: automático diário (free tier: 7 dias)

### Migrations
- Ferramenta: **Alembic** (integrado ao FastAPI)
- Convenção: `YYYY_MM_DD_HHMMSS_descricao_curta.py`
- Rodar em CI: `alembic upgrade head` antes de deploy

### Connection pool
- `asyncpg` com pool de 5–10 conexões (suficiente para single-user)
- Connection string em `DATABASE_URL`

---

## Cache — Redis (Upstash)

### Plano free
- 10.000 comandos/dia
- Com workers rodando 3× ao dia em ~30 assets: ~90–150 comandos/ciclo → bem dentro do free

### Padrão de keys
```
price:b3:{TICKER}               # ex: price:b3:PETR4
price:crypto:{TICKER}           # ex: price:crypto:BTC
price:treasury:{NAME_SLUG}      # ex: price:treasury:selic-2028
wallet:binance:{ACCOUNT}        # snapshot Binance spot+earn
benchmark:cdi:latest
benchmark:ipca:latest
```

### TTLs
```python
TTL_B3 = 4 * 3600          # 4h
TTL_CRYPTO = 2 * 3600      # 2h
TTL_TREASURY = 6 * 3600    # 6h (menos volátil)
TTL_BENCHMARK = 86400      # 24h (CDI/IPCA mudam diariamente)
TTL_WALLET = 4 * 3600      # 4h (wallet scans são pesados)
```

---

## CI/CD — GitHub Actions

### Pipeline
```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: pytest api/tests/ --cov=api --cov-fail-under=80

  deploy-api:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

  deploy-web:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: "--prod"
```

### Repositório
- **Estrutura:** monorepo simples (sem Turborepo — não vale overhead)
```
goodies/
├── api/            # FastAPI
├── web/            # Next.js
├── docs/           # project-context.md, PRD, Arquitetura (links/cópias)
│   ├── 05_Epicos/
│   └── 06_Stories/
├── .github/
├── fly.toml
└── README.md
```

---

## Ferramentas de desenvolvimento

| Ferramenta | Uso |
|---|---|
| `ruff` | Linting + formatting Python (substitui black+flake8) |
| `mypy` | Type checking Python (modo strict) |
| `pytest` + `pytest-cov` | Testes + cobertura |
| `httpx[test]` / `pytest-asyncio` | Testes assíncronos do FastAPI |
| ESLint + Prettier | Linting + formatting TypeScript |
| `pre-commit` | hooks: ruff, mypy, eslint antes de cada commit |

---

## Repositório local (WSL)

```bash
# Path WSL
/projects/goodies

# GitHub (a criar)
git remote add origin https://github.com/vitorvogomes/goodies.git
git push -u origin main
```

**GSD-Pi:** instalar após criar repo e fazer push inicial.
```bash
npm install -g @opengsd/gsd-pi@latest
cd /projects/goodies
gsd    # setup inicial
```

---

*→ [[02_Arquitetura]]*
*→ [[07_Decisoes]]*
*→ [[00_Sistema/MOCs/MOC_Vitor.html]]*
