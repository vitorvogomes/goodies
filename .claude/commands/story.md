---
description: Carrega o contexto de uma story da v2 para implementação. Uso: /story 1.1
---

A story **$ARGUMENTS** está em `docs/v2/planning/epics.md`, na seção `### Story $ARGUMENTS:`. Leia a seção inteira
(até o próximo `### Story` ou `## Epic`): user story, linha **Requisitos** e todos os critérios de aceite. Se a seção não
existir, avise e pare. Leia também a seção `## Epic N` da story (objetivo e notas do épico) e as **Regras para todos os
épicos** do topo do arquivo.

Depois leia:
- `CLAUDE.md` (regras do projeto)
- `.claude/memory/conventions.md` (como escrever o código)
- `.claude/memory/decisions.md` (ADRs — não violar)
- `.claude/memory/skills.md` (roteamento de skills; seção B2 = épico → skills)
- `docs/v2/planning/architecture/architecture-goodies-2026-10-17/ARCHITECTURE-SPINE.md`: os ADs citados pela story
  (no inventário, cada AR cita o AD de origem entre parênteses) e os que governam as engines que ela toca
- Se a story tem UI: as seções de `docs/v2/planning/ux-designs/ux-goodies-2026-10-17/EXPERIENCE.md` e `DESIGN.md`
  dos componentes que ela cita (mesmos nomes nos dois)

Marque a story como `[~]` no `PROGRESS.md`.

## Passo 1 — Resolver as skills

Derive as skills do épico da story pela matriz **B2 (épico v2 → skills)** de `.claude/memory/skills.md`. Imprima:

```
Story: <N.M> <título>  (Marco <k> / Épico <N>)
Requisitos: <linha Requisitos>
Skills desta story:
 • test-driven-development   (sempre)
 • <skill de domínio>        (<por quê>)
 • <skill secundária>        (on-demand, ao chegar no sub-passo)
⚠ Evitar: supabase para auth/RLS/migrations (ADR-006); Alembic é o caminho de migração
```

Se houver lacuna sem skill, diga "sem skill → seguir decisions.md/conventions.md".

## Passo 2 — Invocar as skills

Invoque agora `test-driven-development` + a skill de domínio primária. Skills de UI/design e outras secundárias: só
quando chegar ao sub-passo correspondente.

## Passo 3 — Planejar (TDD-first)

Com base nos critérios de aceite, me diga:
1. O que será implementado (3 linhas)
2. Quais arquivos serão criados ou modificados, e se há revisão Alembic
3. Se a story escreve dado real: o backup pré-migração, o baseline (Story 1.3) e os testes `dados_reais` que vão provar os
   invariantes — e que tudo roda contra `goodies_dev`/`goodies_dados`, nunca contra o banco real
4. Qual é o primeiro teste a escrever (RED)

Aguarde minha confirmação antes de implementar.
