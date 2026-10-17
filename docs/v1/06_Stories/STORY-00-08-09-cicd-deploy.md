---
tipo: story
epico: EPIC-00
story: STORY-00-08-09
titulo: GitHub Actions + Deploy Fly.io e Vercel
status: pendente
estimativa: M (3-4h)
tags: [goodies, story, foundation, cicd, deploy]
skills: [systematic-debugging]  # CI/CD/Fly/Vercel: sem skill → conventions.md
---

# STORY-00-08+09 — CI/CD e Deploy Inicial

**Como** desenvolvedor  
**Quero** que cada push para main dispare testes e deploy automático  
**Para** garantir que produção está sempre no estado atual do main

---

## Critérios de aceite

- [ ] `.github/workflows/deploy.yml` com 3 jobs: `test` → `deploy-api` → `deploy-web`
- [ ] Job `test`: pytest com cobertura ≥ 80%, eslint no frontend
- [ ] Job `deploy-api`: flyctl deploy (só executa se `test` passou)
- [ ] Job `deploy-web`: vercel deploy --prod (só executa se `test` passou)
- [ ] Fly.io: app criado (`goodies-api`), secrets configurados via `flyctl secrets set`
- [ ] Vercel: projeto criado, conectado ao GitHub, env var `NEXT_PUBLIC_API_URL` configurada
- [ ] `GET https://goodies-api.fly.dev/api/v1/health` retorna 200 com Postgres e Redis conectados
- [ ] `https://goodies.vercel.app/login` carrega a tela de login
- [ ] Secrets do GitHub Actions configurados: `FLY_API_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`

## Notas de implementação
- Fly.io: região `gru` (São Paulo) se disponível, senão `iad` (Virginia — mais próxima com Fly.io)
- Primeiro deploy: `flyctl launch` → gera `fly.toml` → ajustar `vm.memory_mb = 256`
- Alembic: adicionar step `alembic upgrade head` no deploy script (Fly.io release command)

## Dependências
STORY-00-02 a STORY-00-07 concluídas (algo para deployar).
