# Rodar o Goodies localmente

**Ambiente de desenvolvimento.** A produção roda no Railway (ADR-018, runbook em `docs/DEPLOY_RAILWAY.md`).
Aqui a stack de dev (Postgres + Redis + **API**) sobe via `docker compose` na porta **8000** e o front (Next.js)
roda no host.

> O `.env` guarda só segredo, PII e o que muda por ambiente; o resto tem padrão em `api/config.py`. `BACKUP_DIR` aponta para um diretório fora do
> repositório e fora de pasta sincronizada com a nuvem. No compose, a API usa `postgres:5432` e `redis:6379` (rede do Docker); o front
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
O serviço `api` aponta para o **banco real**: roda a imagem construída, **sem** bind mount e **sem**
`--reload`. Para pegar código novo: `docker compose up -d --build api`. Na subida
(`scripts.ops.startup`) ele confere `BACKUP_DIR` e o Alembic: com `AUTO_MIGRATE=false` (padrão), banco
fora do `head` não sobe e a mensagem manda rodar `python -m scripts.ops.migrar`.

### 2. Migrations + admin (primeira vez / quando o schema mudar)

> **Banco vazio (instalação nova):** não rode `alembic upgrade head` direto — a 0016 exige um usuário. Suba a api
> com `AUTO_MIGRATE=true` e `ADMIN_EMAIL`/`ADMIN_PASSWORD` na linha de comando (não no `.env`), por exemplo
> `cd api && AUTO_MIGRATE=true ADMIN_EMAIL=… ADMIN_PASSWORD=… uv run python -m scripts.ops.startup`: a subida faz backup → `0002_refresh_token_hash` →
> admin → `head` (mesmo caminho da produção). Depois tire `ADMIN_PASSWORD` do ambiente.
```bash
cd api && uv run python -m scripts.ops.migrar        # main limpa + dados_reais verdes + backup → upgrade

# admin (só na primeira vez; não exponha a senha no chat/repo):
docker compose exec -e ADMIN_EMAIL='vitor@goodies.local' -e ADMIN_PASSWORD='change-me' \
  api python -m scripts.ops.seed_admin
```

### 3. Frontend — Next.js (host)
Em outro terminal:
```bash
cd ~/projects/goodies/web
pnpm dev                                # http://localhost:3000
```
Nenhuma variável é necessária. O browser chama sempre a própria origem (`/api/v1/...`) e o Next repassa à
api em `http://127.0.0.1:8000` (rewrite em `next.config.ts`, igual à produção — ADR-018). Para apontar para outra
api, defina `API_INTERNAL_URL` em `web/.env.local` e **reinicie o `pnpm dev`** (o destino é lido na subida).

Abra `http://localhost:3000/login`, entre com o admin seedado → cai em `/visao-geral/painel`.

---

## Validar a stack

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
DADOS_REAIS_REQUIRED=1 uv run pytest tests/ -q -rs --cov   # fail_under 80 no pyproject
uv run ruff check .
uv run mypy engines workers hermes auth db config.py main.py

# Frontend
cd ~/projects/goodies/web && pnpm test && pnpm lint && pnpm build
```

---

## Inspecionar o banco

**No VS Code (você):** SQLTools já conectado (`localhost:5432`, db `goodies`) — veja as tabelas no
painel lateral e rode SQL no scratch `*.session.sql` (`Ctrl+E` na seleção). O schema **só** muda
via Alembic (`python -m scripts.ops.migrar`), nunca criando tabela à mão.

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
```
> ⚠ **Nunca** `docker compose down -v`: o `-v` apaga o volume `pgdata` — o banco real, a única cópia
> dos seus dados fora dos backups.

---

## Segurança local (Story 1.6 — spine AD-18)

- Portas publicadas só em `127.0.0.1` (8000, 5432, 6379): ninguém na rede alcança api, banco ou Redis.
- Postgres e Redis com senha: `POSTGRES_PASSWORD` e `REDIS_PASSWORD` no `.env` (gere com
  `openssl rand -hex 24`, sem colar no chat); `DATABASE_URL`/`REDIS_URL` do `.env` levam as mesmas senhas.
  O `POSTGRES_PASSWORD` só vale na criação do volume; para trocar a senha num volume existente:
  ```bash
  PG=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
  echo "ALTER USER goodies PASSWORD :'pw';" | \
    docker compose exec -T -e NEWPW="$PG" postgres sh -c 'psql -q -U goodies -d postgres -v pw="$NEWPW" -f /dev/stdin'
  unset PG && docker compose up -d
  ```
- A api lê o `.env` pelo `env_file` do compose (no host, pelo `config.py`) e **não sobe** com segredo
  `dev-insecure-*` fora de `ENVIRONMENT=test`. Trocar os segredos JWT derruba as sessões: faça login de novo.
- Login: 5 tentativas erradas em 15 minutos bloqueiam o e-mail por 15 minutos.
- Hermes desligado na v2.0 (`HERMES_ENABLED=false`): o router não é montado.

---

## Backup e restauração (Story 1.2 — spine AD-18; produção: `docs/DEPLOY_RAILWAY.md` §4)

**Onde:** `BACKUP_DIR` do `.env` — caminho absoluto **fora do repositório** e **fora de pasta
sincronizada com a nuvem** (OneDrive, Dropbox, Google Drive, iCloud): a api recusa subir nesses casos.
O compose monta esse diretório em `/backups` no container.

| Backup | Quando | Onde | Retenção |
|---|---|---|---|
| diário (`db_backup`) | 13:00 BRT, ou no catch-up ao abrir o app se passou de 24 h | `BACKUP_DIR/` | 30 dias por idade + o mais novo de cada um dos 12 meses anteriores |
| pré-migração | antes de toda migração/escrita de dado (`migrar`, `AUTO_MIGRATE`, Alembic manual, `close_retro`, `refechar`) | `BACKUP_DIR/pre-migracao/` | nunca apagado pela rotina |
| conferência (`restore_check`) | dia 1 de cada mês | banco descartável `goodies_restore_check` | — |

Arquivos: `<banco>_<AAAAMMDD_HHMMSS UTC>[_<motivo>].dump` (`pg_dump -Fc`, cliente 15). Os jobs ficam em
`job_runs` como os demais; falha vira aviso de worker. Backup manual:
`cd api && uv run python -m scripts.ops.backup --tag <motivo>`.

**Guarda do Alembic:** `alembic upgrade` contra um banco que não é de teste (`goodies_test`,
`goodies_dados`, `goodies_dev`, `goodies_tmp_*`) exige um backup com menos de 1 h ou faz um antes; se o
backup falhar, não migra.

### Bancos de apoio
- `goodies_dev` — cópia para desenvolver: `uv run python -m scripts.ops.restore_dev_db [--backup <arquivo>]`.
- `goodies_dados` — base dos testes `@pytest.mark.dados_reais`, restaurada do backup pré-migração fixado em
  `api/tests/dados_reais/pinned_backup.txt` (`uv run python -m scripts.ops.restore_dados_db [--backup <arquivo>]`).
  Sem a base os testes são pulados com aviso; o `/gate` e o `migrar` (`DADOS_REAIS_REQUIRED=1`) falham.
- `goodies_test` — suíte unitária (criado e migrado pelo pytest).

### Restaurar o banco real a partir de um backup (recuperação)
```bash
cd ~/projects/goodies
docker compose stop api                                     # nada escrevendo no banco
docker compose exec -T postgres psql -U goodies -d postgres \
  -c 'DROP DATABASE IF EXISTS goodies' -c 'CREATE DATABASE goodies'
docker compose exec -T postgres pg_restore -U goodies -d goodies --no-owner --no-privileges \
  < "$BACKUP_DIR/<arquivo>.dump"                            # (BACKUP_DIR do seu .env)
docker compose exec -T postgres psql -U goodies -d goodies -Atc 'SELECT version_num FROM alembic_version'
# Se o backup veio sem a tabela alembic_version (ex.: dump parcial), marque a revisão dele:
#   cd api && DATABASE_URL=postgresql://goodies:<senha>@localhost:5432/goodies uv run alembic stamp <revisão>
docker compose up -d api                                    # AUTO_MIGRATE=false: só sobe se estiver no head
docker compose exec -T postgres psql -U goodies -d goodies \
  -Atc 'SELECT count(*) FROM transactions' -Atc 'SELECT count(*) FROM asset_operations'
```
Se o backup é de uma revisão anterior ao código, a api não sobe: rode `python -m scripts.ops.migrar`.
O mesmo caminho (restaura → confere contagens) é testado em `api/tests/ops/test_backup_db.py` num banco
descartável e todo dia 1 pelo job `restore_check`.

### Opcional: criptografia e cópia externa
```bash
age-keygen -o ~/.config/goodies/backup.key                  # chave FORA do repo (guarde uma cópia offline)
age -r "$(age-keygen -y ~/.config/goodies/backup.key)" \
  -o /mnt/e/goodies/<arquivo>.dump.age "$BACKUP_DIR/<arquivo>.dump"   # disco externo
age -d -i ~/.config/goodies/backup.key -o /tmp/<arquivo>.dump /mnt/e/goodies/<arquivo>.dump.age
```

---

## Alternativa: backend no host (uv), só infra no Docker
Para iterar no backend sem a imagem (ex.: anexar debugger), suba apenas Postgres+Redis no
Docker e rode o uvicorn no host (a 8000 está livre):
```bash
cd ~/projects/goodies
docker compose up -d postgres redis
cd api
uv run python -m scripts.ops.migrar   # (ou alembic upgrade head: a guarda faz o backup antes)
ADMIN_EMAIL='vitor@goodies.local' ADMIN_PASSWORD='change-me' uv run python -m scripts.ops.seed_admin
uv run uvicorn main:app --reload --port 8000
```
Rodando a partir de `api/`, a API usa `localhost` para Postgres/Redis automaticamente. Não
suba o serviço `api` do compose ao mesmo tempo (conflito na 8000).
