# Goodies API — imagem usada pelo docker compose local. STORY-00-02 · deps via uv (ADR-010).
# bookworm: o cliente do Postgres do Debian 12 é o 15, igual ao servidor do compose (pg_dump 15).
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-15 \
    && rm -rf /var/lib/apt/lists/*

# uv: binário copiado da imagem oficial (sem pip na imagem final).
COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # venv FORA de /app — no compose o bind mount monta ./api em /app e sombrearia /app/.venv.
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    # Story 1.2: backup/restauração com o pg_dump/pg_restore 15 desta imagem.
    PG_TOOLS=local

WORKDIR /app

# Camada de deps (cacheável) — só runtime (--no-dev), lock travado (--frozen).
# package=false (pyproject) → uv instala só as deps, sem precisar do código aqui.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Código da API. pythonpath efetivo = /app (igual ao pytest: pythonpath=["."]).
COPY . .

EXPOSE 8000

# Story 1.2: confere BACKUP_DIR e o head do Alembic (AUTO_MIGRATE=false não migra) e sobe o uvicorn
# sem --reload. Health em GET /api/v1/health.
CMD ["python", "-m", "scripts.ops.startup"]
