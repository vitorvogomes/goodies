"""Cache Redis para preços e métricas de mercado — STORY-00-04.

Decisão de transporte (ADR-001 / CLAUDE.md): usamos `redis.asyncio` (cliente TCP)
sobre uma única variável `REDIS_URL` (Redis 7 do compose, com senha — Story 1.6;
lida via `settings.redis_url`).

Formato de chave (conventions.md / ADR — "Chave de nomes Redis"):
    {engine}:{type}:{identifier}
Ex.: `price:b3:PETR4`, `price:crypto:BTC`, `wallet:binance:spot`, `xirr:consolidated`.

Fail-soft (conventions.md "Nunca HTTP 5xx" / ADR-004): qualquer falha do Redis é
logada via structlog e tratada como cache-miss. Uma indisponibilidade do Redis
NUNCA propaga exceção para o chamador — `get()` devolve None; `set()`/`delete()`
retornam sem efeito.
"""

import json

import redis.asyncio as redis
import structlog

from config import settings

logger = structlog.get_logger()

# Um valor de cache é sempre um objeto JSON (dict). `object` (não `Any`) mantém
# mypy --strict satisfeito sem afrouxar a tipagem dos chamadores.
CacheValue = dict[str, object]


def _resolve_url(redis_url: str | None) -> str:
    """Resolve a URL efetiva: argumento explícito > `settings.redis_url` (REDIS_URL do .env)."""
    if redis_url is not None:
        return redis_url
    return settings.redis_url


class PriceCache:
    """Cache de mercado sobre Redis (asyncio), com semântica fail-soft.

    Valores são serializados em JSON. As chaves seguem o formato
    `{engine}:{type}:{identifier}` (ex.: `price:b3:PETR4`).
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._url = _resolve_url(redis_url)
        # decode_responses=True => Redis devolve str (não bytes) em get/set.
        self._client: redis.Redis = redis.from_url(self._url, decode_responses=True)

    @staticmethod
    def _decode(raw: object) -> CacheValue | None:
        """Desserializa um valor cru do Redis (str|None) → dict, ou None (fail-soft)."""
        if not isinstance(raw, str | bytes | bytearray):
            return None  # ausente (None) ou tipo inesperado
        try:
            data: CacheValue = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("redis_get_decode_failed", error=str(exc))
            return None
        return data

    async def get(self, key: str) -> CacheValue | None:
        """Devolve o dict JSON cacheado, ou None se ausente/erro (fail-soft)."""
        try:
            raw = await self._client.get(key)
        except Exception as exc:  # falha de conexão/timeout do Redis
            logger.warning("redis_get_failed", key=key, error=str(exc))
            return None
        return self._decode(raw)

    async def mget(self, keys: list[str]) -> list[CacheValue | None]:
        """Busca várias chaves numa ida só (substitui N gets no `list_user_prices`).

        Preserva a ordem de `keys`; chave ausente/indecodificável vira None na mesma
        posição. Fail-soft: Redis fora → lista de None do mesmo tamanho (nunca levanta).
        """
        if not keys:
            return []
        try:
            raws = await self._client.mget(keys)
        except Exception as exc:
            logger.warning("redis_mget_failed", error=str(exc))
            return [None] * len(keys)
        return [self._decode(r) for r in raws]

    async def set(self, key: str, data: CacheValue, ttl_seconds: int) -> None:
        """Serializa `data` em JSON e grava com TTL. Fail-soft: não levanta."""
        try:
            await self._client.set(key, json.dumps(data), ex=ttl_seconds)
        except Exception as exc:
            logger.warning("redis_set_failed", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        """Remove a chave. Fail-soft: não levanta."""
        try:
            await self._client.delete(key)
        except Exception as exc:
            logger.warning("redis_delete_failed", key=key, error=str(exc))


async def check_redis(redis_url: str | None = None) -> tuple[str, str]:
    """Health check do Redis para o `/api/v1/health` (registro em market/__init__).

    Retorna `("redis", "connected")` em sucesso e `("redis", "disconnected")` em
    qualquer falha. Fail-soft: nunca levanta exceção.
    """
    url = _resolve_url(redis_url)
    client: redis.Redis = redis.from_url(url, decode_responses=True)
    try:
        await client.ping()
        return ("redis", "connected")
    except Exception as exc:
        logger.warning("redis_health_check_failed", error=str(exc))
        return ("redis", "disconnected")
    finally:
        try:
            await client.aclose()
        except Exception:
            pass
