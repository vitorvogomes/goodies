# Rodar o Goodies localmente

**Docker-local-first:** a stack inteira de dev (Postgres + Redis + **API**) sobe via
`docker compose` na porta **8000**. O front (Next.js) roda no host. Para desenvolver e validar
o m0 você **não precisa** de Supabase, Upstash, Fly nem Vercel — deploy (cloud) fica para
depois, ver [`DEPLOY.md`](DEPLOY.md).

> As variáveis `UPSTASH_*`, `REDIS_URL`, `DISCORD_WEBHOOK_URL` são de produção/m6 — deixe os
> placeholders. No compose, a API usa `postgres:5432` e `redis:6379` (rede do Docker); o front
> aponta para `http://localhost:8000`.

---

## Pré-requisitos
- Docker + Docker Compose
- Node + pnpm (via NVM), para o front no host. Se `pnpm` não for encontrado:
  `source "$NVM_DIR/nvm.sh"`.
- **(Opcional)** [uv](https://docs.astral.sh/uv/) — só para rodar a suíte/lint/types no host
  (pytest/ruff/mypy **não** estão na imagem Docker, que carrega só as deps de runtime). O uv
  cria a venv (`api/.venv`) e baixa o Python 3.12 sozinho.
  Instalar: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

---

## Primeira vez (setup)

```bash
cd ~/projects/goodies

# imagem da API (instala as deps de runtime do backend dentro da imagem)
docker compose build

# deps do frontend (host)
( cd web && pnpm install )
```

**(Opcional) deps do backend no host — só se for rodar pytest/ruff/mypy localmente:**
```bash
( cd api && uv sync )          # cria api/.venv (base + grupo dev) a partir do uv.lock
```

---

## Rodar (cada sessão)

### 1. Subir a stack (Postgres + Redis + API) — Docker, porta 8000
```bash
cd ~/projects/goodies
docker compose build && docker compose up -d   # use --build sempre que mudar deps/Dockerfile
docker compose ps                              # postgres, redis e api "healthy"
```
A API tem bind mount + `--reload`: mudanças no código `api/` recarregam sozinhas, sem rebuild
(o rebuild só é necessário ao mudar `pyproject.toml`/`uv.lock`/`Dockerfile`).

### 2. Migrations + admin (primeira vez / quando o schema mudar)
```bash
docker compose exec api alembic upgrade head        # cria/atualiza o schema (users, refresh_token_hash)

# admin (só na primeira vez; não exponha a senha no chat/repo):
docker compose exec -e ADMIN_EMAIL='vitor@goodies.local' -e ADMIN_PASSWORD='change-me' \
  api python -m scripts.seed_admin
```

### 3. Frontend — Next.js (host)
Em outro terminal:
```bash
cd ~/projects/goodies/web
pnpm dev                                # http://localhost:3000
```
A URL da API já tem default `http://localhost:8000` (`lib/api.ts`). Só defina outra se precisar
— em `web/.env.local` (tem precedência sobre `web/.env`):
`echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local`.

> ⚠️ `NEXT_PUBLIC_*` é **inlined no boot** do `pnpm dev`. Se trocar a URL da API (ou tiver um
> `web/.env` antigo apontando p/ outra porta, ex.: `:8001`), **reinicie o `pnpm dev`** — senão
> o browser continua chamando o valor velho e o login falha com "Não foi possível conectar".

Abra `http://localhost:3000/login`, entre com o admin seedado → cai em `/dashboard`.

---

## Validar o m0

**App no ar (não precisa de uv):**
```bash
# Health (gate local): 200 com postgres+redis conectados
curl -s http://localhost:8000/api/v1/health

# Login (tokens) e rota protegida sem token (401)
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"vitor@goodies.local","password":"change-me"}'
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/auth/me
```

**Suíte de testes + cobertura + lint + types (precisa do uv no host):**
Rodam contra o Postgres/Redis do compose (expostos em `localhost:5432` / `localhost:6379`).
```bash
cd ~/projects/goodies/api
uv run pytest tests/ -v
uv run pytest tests/ --cov=engines --cov-report=term-missing
uv run ruff check .
MYPYPATH=. uv run mypy main.py config.py health.py db/connection.py \
  engines/market/cache.py auth/security.py auth/dependencies.py auth/router.py

# Frontend
cd ~/projects/goodies/web && pnpm lint && pnpm build
```

---

## Inspecionar o banco

**No VS Code (você):** SQLTools já conectado (`localhost:5432`, db `goodies`) — veja as tabelas no
painel lateral e rode SQL no scratch `*.session.sql` (`Ctrl+E` na seleção). O schema **só** muda
via Alembic (`docker compose exec api alembic upgrade head`), nunca criando tabela à mão.

**Por linha de comando (psql no container)** — usado p/ validar migrations/dados nos gates:
```bash
docker compose exec -T postgres psql -U goodies -d goodies -c '\dt'        # listar tabelas
docker compose exec -T postgres psql -U goodies -d goodies -c '\d users'   # descrever tabela
docker compose exec -T postgres psql -U goodies -d goodies -c 'SELECT count(*) FROM users;'
```
Roda dentro do container (não precisa de psql no host). Inspeção é read-only por convenção —
alterações de schema sempre via migration.

---

## Encerrar
```bash
docker compose down        # para os containers (mantém os dados em volume)
docker compose down -v     # zera também o Postgres (volume pgdata)
```

---

## Alternativa: backend no host (uv), só infra no Docker
Para iterar no backend sem a imagem (ex.: anexar debugger), suba apenas Postgres+Redis no
Docker e rode o uvicorn no host (a 8000 está livre):
```bash
cd ~/projects/goodies
docker compose up -d postgres redis
cd api
uv run alembic upgrade head
ADMIN_EMAIL='vitor@goodies.local' ADMIN_PASSWORD='change-me' uv run python -m scripts.seed_admin
uv run uvicorn main:app --reload --port 8000
```
Rodando a partir de `api/`, a API usa `localhost` para Postgres/Redis automaticamente. Não
suba o serviço `api` do compose ao mesmo tempo (conflito na 8000).
