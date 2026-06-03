---
tipo: story
epico: EPIC-00
story: STORY-00-03
titulo: Conectar Supabase (Postgres pool + schema users)
status: pendente
estimativa: M (2-3h)
tags: [goodies, story, foundation, supabase, postgres]
skills: [test-driven-development, supabase-postgres-best-practices, supabase]  # supabase só p/ conexão Postgres — nunca auth
---

# STORY-00-03 — Conectar Supabase

**Como** desenvolvedor  
**Quero** ter o Postgres (Supabase) conectado com pool asyncpg e schema inicial  
**Para** que o backend possa persistir dados

---

## Critérios de aceite

- [ ] Projeto Supabase criado na região sa-east-1 (São Paulo)
- [ ] `api/db/connection.py` com pool asyncpg (min 2, max 10 conexões)
- [ ] `api/db/migrations/` com Alembic configurado
- [ ] Migration inicial: tabela `users` com `id`, `email`, `password_hash`, `created_at`
- [ ] `alembic upgrade head` roda sem erro
- [ ] `GET /api/v1/health` atualizado para incluir status do Postgres:
  ```json
  {
    "status": "ok",
    "postgres": "connected"
  }
  ```
- [ ] Teste: conexão com Postgres, insert e select na tabela `users`
- [ ] RLS habilitado na tabela `users`

## Notas de implementação
- Connection string: `DATABASE_URL` em `.env` (Supabase fornece a string completa)
- Usar `asyncpg` direto (sem SQLAlchemy ORM) — mais performático e mais simples para queries SQL escritas à mão
- Seed: criar usuário `admin` (Vitor) com senha hasheada via bcrypt na migration inicial ou via script separado

## Dependências
STORY-00-02 concluída.
