---
tipo: epico
projeto: Goodies
epico: EPIC-00
milestone: m0-foundation
titulo: Foundation — Bootstrap do projeto
status: pendente
tags: [goodies, epic, foundation, infra]
---

# EPIC-00 — Foundation

**Milestone:** m0-foundation  
**Objetivo:** Monorepo configurado, FastAPI + Next.js rodando, Supabase conectado, Redis conectado, auth JWT funcional, CI/CD ativo.  
**Gate de saída:** `GET /api/v1/health` retorna 200 com Postgres e Redis conectados. Login funciona. Deploy automático no Fly.io e Vercel via push para main.

---

## Escopo

Este épico não entrega nenhuma feature de negócio. Entrega **infraestrutura confiável** sobre a qual todos os outros épicos são construídos.

### Inclui:
- Criação do repositório GitHub
- Estrutura de monorepo (`api/`, `web/`, `docs/`)
- FastAPI com Uvicorn, health check endpoint
- Next.js 16 com App Router e TypeScript (ADR-009)
- Supabase: projeto criado, schema inicial (tabela `users`), connection pool
- Redis (Upstash): conta criada, conexão testada
- JWT auth: login, refresh, middleware de autenticação
- Tela de login no Next.js
- GitHub Actions: pipeline de test + deploy
- Fly.io: app criado, secrets configurados
- Vercel: projeto conectado ao GitHub
- `pre-commit` hooks configurados (ruff, mypy, eslint)
- `project-context.md` no repo (gerado nesta sessão)

### Não inclui:
- Qualquer tabela de dados financeiros (vêm nos épicos seguintes)
- Workers de preço
- Features de Ledger, Portfolio, Market ou Analytics

---

## Stories

- STORY-00-01: Criar monorepo e estrutura de pastas
- STORY-00-02: Setup FastAPI com health check
- STORY-00-03: Conectar Supabase (Postgres pool + schema users)
- STORY-00-04: Conectar Redis (Upstash)
- STORY-00-05: Implementar auth JWT (login, refresh, middleware)
- STORY-00-06: Setup Next.js com TypeScript e Tailwind
- STORY-00-07: Tela de login no frontend
- STORY-00-08: Configurar GitHub Actions (test + deploy)
- STORY-00-09: Deploy inicial Fly.io + Vercel

---

## Dependências
Nenhuma — este épico é o ponto de partida.

## Bloqueados por este épico
EPIC-01, EPIC-02, EPIC-03, EPIC-04, EPIC-05, EPIC-06, EPIC-07 (todos dependem da foundation)
