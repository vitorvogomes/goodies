# Deploy — Goodies (m0)

Pipeline: push em `main` → GitHub Actions (`.github/workflows/deploy.yml`):
`test` (pytest cov ≥ 80% + ruff + mypy + eslint) → `deploy-api` (Fly.io) + `deploy-web` (Vercel).

> Segredos vivem só nos secrets do provedor / `fly secrets` — nunca no repo (security.md).
> Para logins interativos, rode você mesmo na sessão com `! <comando>`.

## Passos manuais (uma vez)

### 1. Supabase (Postgres, região sa-east-1)
Criar projeto → connection string → `DATABASE_URL` (`postgresql://...`).

### 2. Upstash (Redis)
Criar Redis DB → endpoint TLS → `REDIS_URL` (`rediss://default:<token>@<host>:6379`).

### 3. Fly.io (API) — a partir de `api/`
```bash
flyctl auth login
flyctl launch --no-deploy --name goodies-api --region gru   # já há api/fly.toml — reaproveitar
flyctl secrets set \
  DATABASE_URL='...' REDIS_URL='...' \
  JWT_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')" \
  JWT_REFRESH_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')" \
  HERMES_SERVICE_TOKEN_SECRET="$(python -c 'import secrets;print(secrets.token_hex(32))')"
flyctl deploy   # o release_command roda `alembic upgrade head`
```
Pós-deploy (criar admin + token Hermes):
```bash
ADMIN_EMAIL='...' ADMIN_PASSWORD='...' flyctl ssh console -C "python -m scripts.seed_admin"
flyctl ssh console -C "python -m scripts.gen_hermes_token"   # guardar no secret do Hermes
```

### 4. Vercel (web)
- Importar o repo no Vercel com **Root Directory = `web`**.
- Env var: `NEXT_PUBLIC_API_URL = https://goodies-api.fly.dev`.
- `vercel link` → copiar `VERCEL_ORG_ID` e `VERCEL_PROJECT_ID` de `.vercel/project.json`.

### 5. Secrets do GitHub Actions (repo → Settings → Secrets → Actions)
`FLY_API_TOKEN` (`flyctl tokens create deploy`), `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.

## Gate m0 (verificar após o deploy)
- `GET https://goodies-api.fly.dev/api/v1/health` → 200 com `postgres: connected` e `redis: connected`.
- `https://goodies.vercel.app/login` carrega a tela de login.

> Nota: a config lê `ENVIRONMENT`; o `fly.toml` define `ENV=production`. O label `environment`
> no /health mostrará "development" até alinharmos a chave (follow-up — não bloqueia o gate).
