---
tipo: story
epico: EPIC-00
story: STORY-00-04
titulo: Conectar Redis (Upstash)
status: pendente
estimativa: S (1h)
tags: [goodies, story, foundation, redis, cache]
---

# STORY-00-04 — Conectar Redis

**Como** desenvolvedor  
**Quero** ter Redis (Upstash) conectado e testado  
**Para** que o cache de preços funcione nos épicos seguintes

---

## Critérios de aceite

- [ ] Conta Upstash criada, banco Redis configurado
- [ ] `api/engines/market/cache.py` com classe `PriceCache`:
  - `get(key) → Optional[dict]`
  - `set(key, data, ttl_seconds)`
  - `delete(key)`
- [ ] `GET /api/v1/health` inclui status Redis: `"redis": "connected"`
- [ ] Teste: set + get + expiração de key no Redis
- [ ] Fallback: se Redis indisponível, `get()` retorna `None` sem exception (log de warning)

## Notas de implementação
- Usar `redis.asyncio` (biblioteca `redis[asyncio]`)
- Conexão via `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` (REST API do Upstash — não TCP direto)
- Keys no formato `{engine}:{type}:{identifier}` (ex: `price:b3:PETR4`)

## Dependências
STORY-00-02 concluída.
