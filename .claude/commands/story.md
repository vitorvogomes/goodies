---
description: Carrega contexto de uma story para implementação. Uso: /story 00-01
---

Carregue e leia o arquivo `docs/06_Stories/STORY-$ARGUMENTS.md`.

Depois leia também:
- `CLAUDE.md` (regras do projeto)
- `.claude/memory/conventions.md` (como escrever o código)
- `.claude/memory/decisions.md` (decisões arquiteturais — não violar)
- `.claude/memory/skills.md` (roteamento de skills)

## Passo 1 — Resolver as skills desta story

1. Leia o frontmatter da story: campos `skills:` e `skills_evitar:`.
2. Se a story **não** tiver `skills:`, derive da **matriz milestone → skills** em
   `.claude/memory/skills.md` (seção B), pelo prefixo do ID (00→m0, 01→m1, …).
3. Imprima um bloco assim (preencha com os valores reais):

   ```
   Story: <título>  (<milestone> / <épico>)
   Skills desta story:
    • test-driven-development   (sempre)
    • <skill de domínio>        (<por quê>)
    • <skill secundária>        (on-demand, ao chegar no sub-passo)
   ⚠ Evitar: <skills_evitar> — <motivo, ex.: ADR-006>
   ```
   Se houver lacuna sem skill (Redis, worker, fetcher, scipy/XIRR, CI/CD), diga
   explicitamente "sem skill → seguir decisions.md/conventions.md".

## Passo 2 — Invocar as skills

- **Invoque agora** (via Skill tool): `test-driven-development` + a skill de domínio
  primária da story.
- Skills de UI/design (`frontend-design`, `ui-ux-pro-max`, `next-best-practices`) e
  outras secundárias: invoque **on-demand**, só ao iniciar o sub-passo correspondente
  (evita inchar o contexto com skills grandes).
- **Respeite `skills_evitar`** — não use essas skills nesta story (ex.: `supabase`
  nunca para auth, ADR-006).

## Passo 3 — Planejar a implementação (TDD-first)

Com base nos critérios de aceite da story, me diga:
1. O que será implementado (resumo em 3 linhas)
2. Quais arquivos serão criados/modificados
3. Qual é o primeiro teste a escrever (TDD: RED primeiro)

Aguarde minha confirmação antes de começar a implementar.
