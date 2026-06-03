"""STORY-00-02 — health check do FastAPI.

RED-first: este teste falha enquanto `main.app` e o endpoint não existem.
Usa httpx.ASGITransport (httpx>=0.27) para chamar o app ASGI sem subir servidor.
"""

import httpx

from main import app


async def test_health_check_returns_200_and_expected_body():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"
