---
tipo: story
epico: EPIC-00
story: STORY-00-01
titulo: Criar monorepo e estrutura de pastas
status: pendente
estimativa: S (< 1h)
tags: [goodies, story, foundation, setup]
---

# STORY-00-01 — Criar monorepo e estrutura de pastas

**Como** desenvolvedor iniciando o projeto  
**Quero** criar o repositório Git com a estrutura de monorepo definida  
**Para** ter uma base organizada onde todos os outros componentes serão adicionados

---

## Critérios de aceite

- [ ] Repositório GitHub `vitorcggomes/goodies` criado (público ou privado — escolha do Vitor)
- [ ] Branch principal: `main` com proteção (requerer PR para merge em produção — opcional no MVP)
- [ ] Estrutura de pastas criada:
  ```
  goodies/
  ├── api/
  │   ├── engines/
  │   │   ├── ledger/
  │   │   ├── portfolio/
  │   │   ├── market/
  │   │   └── analytics/
  │   ├── workers/
  │   ├── hermes/
  │   ├── auth/
  │   └── db/
  ├── web/
  │   ├── app/
  │   ├── components/
  │   └── lib/
  ├── docs/
  │   ├── 05_Epicos/
  │   └── 06_Stories/
  ├── .github/
  │   └── workflows/
  ├── fly.toml (placeholder)
  └── README.md
  ```
- [ ] `.gitignore` cobrindo: `__pycache__`, `.env`, `node_modules`, `.venv`, `.gsd/`
- [ ] `README.md` com: o que é o projeto, stack, links para docs no vault
- [ ] `pre-commit` configurado com hooks básicos (ruff, eslint)
- [ ] `.env.example` com todas as env vars necessárias (sem valores reais)

## Notas de implementação
- Usar `pyproject.toml` no `api/` em vez de `setup.py` (padrão moderno Python)
- Usar `pnpm` para o frontend (`web/`) — mais rápido que npm para monorepos

## Dependências
Nenhuma.
