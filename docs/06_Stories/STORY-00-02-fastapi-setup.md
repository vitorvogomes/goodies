---
tipo: story
epico: EPIC-00
story: STORY-00-02
titulo: Setup FastAPI com health check
status: pendente
estimativa: S (1-2h)
tags: [goodies, story, foundation, fastapi]
---

# STORY-00-02 — Setup FastAPI com health check

**Como** desenvolvedor  
**Quero** ter o FastAPI inicializado com configuração de base e endpoint de health check  
**Para** verificar que o backend está funcionando antes de adicionar qualquer feature

---

## Critérios de aceite

- [ ] `api/main.py` com instância FastAPI, CORS configurado, routers registrados
- [ ] `api/config.py` com `Settings` via pydantic-settings (lê do `.env`)
- [ ] Endpoint `GET /api/v1/health` retorna:
  ```json
  {
    "status": "ok",
    "version": "0.1.0",
    "environment": "development"
  }
  ```
- [ ] Dockerfile em `api/Dockerfile` funcional (build + run localmente)
- [ ] `docker-compose.yml` na raiz para dev local: FastAPI + Postgres + Redis
- [ ] `requirements.txt` com todas as dependências pinadas
- [ ] `requirements-dev.txt` com dependências de teste (pytest, httpx, etc.)
- [ ] Teste: `test_health_check.py` com `httpx.AsyncClient` verificando 200 e corpo

## Notas de implementação
```python
# main.py — estrutura mínima
from fastapi import FastAPI
from api.config import settings

app = FastAPI(title="Goodies API", version="0.1.0")

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "environment": settings.environment}
```

CORS origins: `settings.cors_origins` (list from env var, default `["http://localhost:3000"]`).

## Dependências
STORY-00-01 concluída.
