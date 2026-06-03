"""STORY-00-05 — rotas de auth (login/refresh/me) contra Postgres local."""

import uuid

import httpx
import pytest_asyncio

from auth.security import hash_password
from main import app

_PASSWORD = "correct-horse-battery"


@pytest_asyncio.fixture
async def test_user(pool):
    email = f"login-{uuid.uuid4().hex[:8]}@example.com"
    async with pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email,
            hash_password(_PASSWORD),
        )
    yield {"id": str(uid), "email": email}
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE id = $1", uid)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_login_success_returns_tokens(test_user):
    async with _client() as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": _PASSWORD},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["expires_in"] == 15 * 60


async def test_login_wrong_password_returns_401(test_user):
    async with _client() as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": "wrong"},
        )
    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(pool):
    async with _client() as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "x"},
        )
    assert resp.status_code == 401


async def test_me_requires_valid_token(test_user):
    async with _client() as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": _PASSWORD},
        )
        access = login.json()["access_token"]
        ok = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        no_token = await client.get("/api/v1/auth/me")
        bad = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert ok.status_code == 200
    assert ok.json()["email"] == test_user["email"]
    assert no_token.status_code == 401
    assert bad.status_code == 401


async def test_refresh_returns_new_access_and_rejects_invalid(test_user):
    async with _client() as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": _PASSWORD},
        )
        refresh = login.json()["refresh_token"]
        ok = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        bad = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.token"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]
    assert bad.status_code == 401
