"""Aplicação FastAPI do Goodies — STORY-00-02.

Instância base + CORS + endpoint de health check. As checagens de componentes
(Postgres em 00-03, Redis em 00-04) serão plugadas ao health via registro,
mantendo este arquivo estável entre stories.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from health import collect_component_status

app = FastAPI(title="Goodies API", version=settings.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.version,
        "environment": settings.environment,
        **await collect_component_status(),
    }
