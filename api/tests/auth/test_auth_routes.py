"""STORY-00-05 — rotas de auth (login/refresh/me) contra Postgres local."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from jose import jwt

from auth.security import _ALGORITHM, hash_password, hash_token
from config import settings
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
    # ADR-006: refresh token vai SÓ no cookie httpOnly, nunca no body (legível por JS).
    assert "refresh_token" not in data
    assert data["expires_in"] == 15 * 60


async def test_login_sets_httponly_refresh_cookie(test_user):
    async with _client() as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": _PASSWORD},
        )
    set_cookie = resp.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "httponly" in set_cookie.lower()


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
        await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": _PASSWORD},
        )
        # Refresh agora só sai no cookie httpOnly (jar do client).
        refresh = client.cookies.get("refresh_token")
        ok = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        bad = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.token"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]
    assert bad.status_code == 401


async def test_refresh_via_cookie_returns_new_access(test_user):
    """Browser não lê o cookie httpOnly: o refresh deve funcionar só com o cookie."""
    async with _client() as client:
        await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": _PASSWORD},
        )
        # O cookie de refresh está no jar do client; refresh SEM body usa o cookie.
        resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_refresh_without_token_returns_401(pool):
    """Sem cookie e sem body → 401 (não 422)."""
    async with _client() as client:
        resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_refresh_rotates_cookie_and_db_hash(pool, test_user):
    async with _client() as client:
        await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": _PASSWORD},
        )
        first_refresh = client.cookies.get("refresh_token")
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert resp.status_code == 200
    # Rotação: novo cookie setado na resposta.
    assert "refresh_token=" in resp.headers.get("set-cookie", "")
    # O hash no DB mudou (não é mais o do primeiro refresh).
    async with pool.acquire() as conn:
        stored = await conn.fetchval(
            "SELECT refresh_token_hash FROM users WHERE id = $1",
            uuid.UUID(test_user["id"]),
        )
    assert stored != hash_token(first_refresh)


def _token_with_type(secret: str, *, sub: str, token_type: str) -> str:
    """Forja um JWT com `type` arbitrário assinado por `secret` (p/ os testes de hardening)."""
    payload = {
        "sub": sub,
        "type": token_type,
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    return str(jwt.encode(payload, secret, algorithm=_ALGORITHM))


async def test_me_rejects_token_with_wrong_type(test_user):
    """Token assinado com o segredo de access mas type!=access → 401."""
    forged = _token_with_type(settings.jwt_secret_key, sub=test_user["id"], token_type="refresh")
    async with _client() as client:
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


async def test_refresh_rejects_token_with_wrong_type(test_user):
    """Token assinado com o segredo de refresh mas type!=refresh → 401."""
    forged = _token_with_type(
        settings.jwt_refresh_secret_key, sub=test_user["id"], token_type="access"
    )
    async with _client() as client:
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": forged})
    assert resp.status_code == 401


async def test_refresh_cookie_is_lax_and_not_secure_in_localhost(test_user):
    # Story 1.9 (AD-18): httpOnly, samesite=lax e sem `secure` (localhost não tem HTTPS).
    async with _client() as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": _PASSWORD},
        )
    attrs = [a.strip().lower() for a in resp.headers["set-cookie"].split(";")]
    assert "httponly" in attrs and "samesite=lax" in attrs
    assert "secure" not in attrs


async def test_cors_only_allows_localhost_3000():
    async with _client() as client:
        ok = await client.options(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        bad = await client.options(
            "/api/v1/health",
            headers={"Origin": "http://192.168.0.10:3000", "Access-Control-Request-Method": "GET"},
        )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert ok.headers.get("access-control-allow-credentials") == "true"
    assert "access-control-allow-origin" not in bad.headers
    assert settings.cors_origins == ["http://localhost:3000"]
