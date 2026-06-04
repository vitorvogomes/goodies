# Goodies API — imagem de produção (Fly.io). STORY-00-02 · deps via uv (ADR-010).
FROM python:3.12-slim

# uv: binário copiado da imagem oficial (sem pip na imagem final).
COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # venv FORA de /app — no compose o bind mount monta ./api em /app e sombrearia /app/.venv.
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

# Camada de deps (cacheável) — só runtime (--no-dev), lock travado (--frozen).
# package=false (pyproject) → uv instala só as deps, sem precisar do código aqui.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Código da API. pythonpath efetivo = /app (igual ao pytest: pythonpath=["."]).
COPY . .

EXPOSE 8000

# Sem --reload em produção. uvicorn/alembic vêm de /opt/venv (PATH). Health em GET /api/v1/health.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
