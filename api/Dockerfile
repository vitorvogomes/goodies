# Goodies API — imagem de produção (Fly.io). STORY-00-02.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Camada de deps (cacheável) — instala antes de copiar o código.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da API. pythonpath efetivo = /app (igual ao pytest: pythonpath=["."]).
COPY . .

EXPOSE 8000

# Sem --reload em produção. Health em GET /api/v1/health.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
