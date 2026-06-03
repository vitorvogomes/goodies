"""STORY-00-03/00-04 — o /api/v1/health agrega Postgres + Redis conectados.

Integração: inicializa o pool e bate no endpoint (httpx ASGITransport) com os
serviços locais do docker-compose no ar.
"""

import httpx

from db.connection import close_pool, init_pool
from main import app

DEV_DSN = "postgresql://goodies:goodies@localhost:5432/goodies"


async def test_health_reports_postgres_and_redis_connected():
    await init_pool(DEV_DSN)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/health")
    finally:
        await close_pool()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["postgres"] == "connected"
    assert data["redis"] == "connected"
