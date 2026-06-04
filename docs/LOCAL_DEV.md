# Rodar o Goodies localmente

**Docker-local-first:** para desenvolver e validar o m0 você **não precisa** de Supabase,
Upstash, Fly nem Vercel. Postgres e Redis vêm de containers; a API e o front rodam no host.
Deploy (cloud) fica para depois — ver [`DEPLOY.md`](DEPLOY.md).

> As variáveis `UPSTASH_*`, `REDIS_URL`, `DISCORD_WEBHOOK_URL` são de produção/m6 — deixe os
> placeholders. Localmente a API usa `localhost:5432` (Postgres) e `localhost:6379` (Redis) por
> default, sem ler esses valores.

---

## Pré-requisitos
- Docker + Docker Compose
- Python 3.12 (venv em `api/.venv`)
- Node + pnpm (via NVM). Se `pnpm` não for encontrado: `source "$NVM_DIR/nvm.sh"`.

> ⚠️ A porta **8000** pode estar ocupada por outro processo na sua máquina — por isso a API
> roda na **8001** neste guia.

---

## Primeira vez (setup)

```bash
cd ~/projects/goodies

# backend: venv + dependências
python3 -m venv api/.venv
api/.venv/bin/pip install -r api/requirements-dev.txt

# frontend: dependências
pnpm -C web install
```

---

## Rodar (cada sessão)

### 1. Postgres + Redis (Docker)
```bash
cd ~/projects/goodies
docker compose up -d postgres redis
docker compose ps                       # ambos "healthy"
```

### 2. Backend — FastAPI (host, a partir de `api/`)
```bash
cd ~/projects/goodies/api
.venv/bin/alembic upgrade head          # cria/atualiza o schema (users, refresh_token_hash)

# admin (só na primeira vez; não exponha a senha no chat/repo):
ADMIN_EMAIL='vitor@goodies.local' ADMIN_PASSWORD='change-me' \
  .venv/bin/python -m scripts.seed_admin

.venv/bin/uvicorn main:app --reload --port 8001
```
Rodando a partir de `api/`, a API usa `localhost` para Postgres/Redis automaticamente.

### 3. Frontend — Next.js (host)
Em outro terminal:
```bash
cd ~/projects/goodies/web
echo 'NEXT_PUBLIC_API_URL=http://localhost:8001' > .env.local   # só na primeira vez
pnpm dev                                # http://localhost:3000
```
Abra `http://localhost:3000/login`, entre com o admin seedado → cai em `/dashboard`.

---

## Validar o m0

```bash
# Health (gate local): 200 com postgres+redis conectados
curl -s http://localhost:8001/api/v1/health

# Login (tokens) e rota protegida sem token (401)
curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"vitor@goodies.local","password":"troque-aqui"}'
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/api/v1/auth/me

# Suíte de testes (precisa pg+redis no ar) + cobertura + lint + types
cd ~/projects/goodies/api
.venv/bin/python -m pytest tests/ -v
.venv/bin/python -m pytest tests/ --cov=engines --cov-report=term-missing
.venv/bin/ruff check .
MYPYPATH=. .venv/bin/mypy --config-file pyproject.toml \
  main.py config.py health.py db/connection.py engines/market/cache.py \
  auth/security.py auth/dependencies.py auth/router.py

# Frontend
pnpm -C ~/projects/goodies/web lint
pnpm -C ~/projects/goodies/web build
```

---

## Encerrar
```bash
docker compose down        # para os containers (mantém os dados em volume)
docker compose down -v     # zera também o Postgres (volume pgdata)
```

---

## Alternativa: tudo em Docker
A API também roda em container (hot-reload via bind mount). Como a 8000 pode estar ocupada,
ajuste a porta em `docker-compose.yml` (`- "8000:8000"` → `- "8010:8000"`) e:
```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec -e ADMIN_EMAIL=... -e ADMIN_PASSWORD=... api python -m scripts.seed_admin
curl -s http://localhost:8010/api/v1/health
```
Nesse caso, ajuste `web/.env.local` para `NEXT_PUBLIC_API_URL=http://localhost:8010`.
