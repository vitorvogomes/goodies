---
description: Mostra estado atual do projeto — milestone, stories feitas e próxima pendente
---

Leia `PROGRESS.md` e retorne:

1. **Milestone atual** — primeiro milestone com stories PENDING ou IN_PROGRESS
2. **Progresso** — X de Y stories concluídas neste milestone (contar [x] vs total)
3. **Próxima story** — primeira linha com `[ ]` no milestone atual
4. **Gate do milestone** — critério de saída (está na seção do milestone)
5. **Bloqueadores** — alguma story marcada como `[!]`?

Formato de saída:
```
Milestone: m0-foundation
Progresso: 3/8 stories concluídas
Próxima: STORY-00-04 — Conectar Redis (Upstash)
Gate: GET /api/v1/health → 200 com Postgres + Redis
Bloqueadores: nenhum
```
