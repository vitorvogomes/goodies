---
description: Mostra o estado da v2 — marco, épico, stories feitas e próxima pendente
---

Leia `PROGRESS.md` (v2) e retorne:

1. **Marco atual** — o primeiro marco com story `[ ]` ou `[~]`
2. **Progresso** — stories `[x]` / total no marco e no backlog (78)
3. **Em andamento** — stories `[~]`
4. **Próxima story** — a primeira `[ ]` do marco atual, com o título; confirme o título na seção `### Story N.M` de
   `docs/v2/planning/epics.md`
5. **Gate do marco** — o bloco "Gate marco k" do `PROGRESS.md`
6. **Bloqueadores** — stories `[!]`

Com as 78 stories `[x]` (v2.0 concluída), diga isso e mostre no lugar da próxima story: os gates pendentes do
`PROGRESS.md` (hoje só o m4, nas métricas de uso) e as pendências abertas de `docs/v2/PENDENCIAS-VITOR.md`.

Formato:
```
Marco: 1 — Ritual confiável (Épicos 1–5)
Progresso: 3/44 no marco · 3/78 no total
Em andamento: —
Próxima: 1.4 — Fundação visual — shadcn, tokens e tema
Gate: /gate m1 (ver PROGRESS.md)
Bloqueadores: nenhum
```
