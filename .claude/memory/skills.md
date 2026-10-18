# Skills — Roteamento por story / milestone

> **Fonte autoritativa de roteamento de skills.** O comando `/story` consulta este
> arquivo (+ o frontmatter `skills:` da story) para anunciar e invocar as skills certas.
> Skills só disparam de forma confiável quando **surfaçadas explicitamente** — não
> confie no auto-trigger sozinho (ver guardrails no fim).

## A) Área de trabalho → skill (unidade atômica)

| Área de trabalho | Skill(s) a acionar |
|---|---|
| Schema Postgres, migrations, views | `supabase-postgres-best-practices` (+ `supabase` só p/ contexto de conexão) |
| Otimização SQL, índices, EXPLAIN ANALYZE | `supabase-postgres-best-practices` |
| Design de endpoint REST (status, paginação, versionamento) | `api-design-principles` + `fastapi` (padrões FastAPI/Pydantic atuais) |
| Implementar qualquer feature/bugfix (**sempre**) | `test-driven-development` |
| Bug difícil / correção numérica / falha de teste | `systematic-debugging` |
| Next.js App Router, RSC, file conventions | `next-best-practices` ⚠ surfaçar via `/story` (não auto-dispara) |
| Componente / página / UI production-grade | `frontend-design` + `shadcn` (componentes, `components.json`, registry) |
| Design system: tokens Tailwind v4, paleta, fonts, tipos de chart, UX | `tailwind-design-system` + `ui-ux-pro-max` (+ `better-colors`, `better-typography`) |
| Tabelas de dados (ordenar, filtrar, paginar, agrupar) | `tanstack-table` (+ `shadcn` data-table) |
| Layout / navegação / hierarquia de informação | `better-layout` |
| Polimento de UI (raios, alinhamento, profundidade, hit areas) | `better-ui` + `emil-design-eng` |
| Acessibilidade (contraste, foco, teclado, ARIA) | `better-accessibility` |
| Microcopy pt-BR (rótulos, estados vazios, erros) | `better-writing` |
| **Revisão de UI antes do `/done`** (story de frontend) | `interface-review` (ou `better-interface` p/ passe completo) |
| App Router avançado (streaming, parallel/intercepting routes p/ drawers) | `nextjs-app-router-patterns` + `next-best-practices` |
| Testes de frontend (componentes, hooks, utils) | `vitest-testing` |
| Procurar skill para uma lacuna | `find-skills` (critério: fonte oficial ou ≥1K installs; auditar antes) |
| Logs (structlog), Sentry, métricas, tracing | `python-observability` |
| Redis cache, worker APScheduler, fetcher httpx, scipy/XIRR, CI/CD | **sem skill** → `decisions.md` + `conventions.md` + TDD/`systematic-debugging` |

## B) Matriz milestone → skills

> Cobre as ~90 stories que existem só como linha no `PROGRESS.md`. Quando uma story
> vira arquivo em `docs/v1/06_Stories/`, ela recebe o frontmatter `skills:` (seção C).

| Milestone | Skills que devem ser acionadas | Lacunas (sem skill → conventions/decisions) |
|---|---|---|
| **m0** Foundation | tdd, api-design-principles, supabase-postgres-best-practices, supabase¹, next-best-practices, frontend-design, ui-ux-pro-max, systematic-debugging | Redis conn |
| **m1** Ledger | tdd, supabase-postgres-best-practices, api-design-principles, frontend-design, ui-ux-pro-max, next-best-practices, systematic-debugging | migração CSV |
| **m2** Portfolio | tdd, systematic-debugging, supabase-postgres-best-practices, api-design-principles, frontend-design, ui-ux-pro-max | XIRR/scipy, migração CSV |
| **m3** Market | tdd, api-design-principles, systematic-debugging, frontend-design, ui-ux-pro-max | Redis cache, fetcher httpx, worker APScheduler |
| **m4** Broker | tdd, systematic-debugging, frontend-design, ui-ux-pro-max | fetcher, worker; **Liquid = ADR-005 (client dedicado)** |
| **m5** Analytics | tdd, systematic-debugging, api-design-principles, supabase-postgres-best-practices, frontend-design, ui-ux-pro-max | projeção/anuidade scipy |
| **m6** Observability | **python-observability**, tdd, systematic-debugging, api-design-principles | rate limiting (slowapi) |
| **m7** Frontend | next-best-practices, frontend-design, ui-ux-pro-max, tdd, systematic-debugging | — |

¹ `supabase` em m0 **só** para contexto de conexão Postgres — **nunca** auth (ver guardrails).

### B2) Goodies v2 — épico → skills (substitui m5–m7 quando o BMAD fechar o backlog v2)

| Épico v2 | Skills |
|---|---|
| A. Fundação UI (shadcn, tokens, DataTable, AppShell 4 áreas) | shadcn, tailwind-design-system, tanstack-table, better-layout, better-ui, next-best-practices, vitest-testing, interface-review |
| B. Categorização dinâmica (grupo+sub, inbox, regras) | tdd, supabase-postgres-best-practices, api-design-principles, fastapi, tanstack-table, better-writing |
| C. Ingestão unificada (hub Nubank+B3, lotes, proveniência) | tdd, systematic-debugging, supabase-postgres-best-practices, fastapi, better-layout |
| D. Conciliação e atualização (jobs, CDI real, RF) | tdd, systematic-debugging, python-observability |
| E. Visão geral integrada | ui-ux-pro-max, better-interface, emil-design-eng, nextjs-app-router-patterns |
| F. Observabilidade / deploy / alertas | python-observability, tdd, api-design-principles |

## C) Frontmatter `skills:` nas stories

Toda story em `docs/v1/06_Stories/STORY-*.md` declara, ao lado de `tags:`:
```yaml
skills: [test-driven-development, <skill-de-área>]
skills_evitar: [supabase]   # só onde há risco de misfire (ex.: auth)
```
`/story` lê esse bloco; se ausente, deriva da matriz (B) pelo milestone da story.

## D) Built-in (não precisa instalar)
- Review de PR/diff → comando `/code-review` + agente `code-reviewer` (nativos).
- Security review → comando `/security-review` (nativo).

## E) Guardrails (evitar disparo errado)

- **`supabase` → SÓ contexto Postgres/SQL.** Neste projeto Supabase é apenas a
  connection string do Postgres. Portanto:
  - ❌ **Nunca** para auth/JWT/login/sessions — auth é JWT custom no FastAPI (ADR-006).
  - ❌ Nada de `supabase-js`, RLS, Edge Functions, Realtime, Storage.
  - ❌ Nada de Supabase CLI para migrations — migrations são **Alembic**.
  - Para SQL/schema puro, prefira `supabase-postgres-best-practices`.
- **`next-best-practices`** tem trigger passivo + `user-invocable:false` → só entra se
  `/story` surfaçar; não conte com auto-trigger.
- **`nextjs-supabase-auth`** — IGNORAR (auth custom, ADR-006).
- **`frontend-workflow` / `backend-workflow`** (Flash Capital) — se ativarem, priorizar
  `CLAUDE.md` + `decisions.md`.

## F) Lacunas sem skill (decisão consciente)

Áreas sem skill instalada → seguir `decisions.md` (TTLs, key naming, fallback, ADR-005) +
`conventions.md` + TDD/`systematic-debugging`:
**Redis cache** · **worker APScheduler** · **fetcher httpx/retry** · **scipy/XIRR numérico** ·
**rate limiting**. (CI/CD removido; deploy volta na v2.1.)

Candidatos avaliados e **não instalados** (sem fonte de bom fit no registry):

| Necessidade | Candidato | Por que não |
|---|---|---|
| Redis cache TTL | `redis/agent-skills@redis-semantic-cache` | é cache *semântico/vetorial*, não TTL key-value |
| CSV/migração | `pluginagentmarketplace@pandas-data-analysis` | "análise" pandas, não ETL determinístico; publisher pouco conhecido |

Para instalar mesmo assim: `npx skills find "<termo>"` e validar a fonte antes.

## D) Instalação de skills (layout do repo)

- Skills vivem **só** em `.claude/skills/<nome>/` (diretórios reais, versionados). A pasta
  `.agents/` foi removida em 2026-10-17 — não recriar.
- Instalar com alvo exclusivo Claude Code: `npx skills add <owner/repo> --skill <nome> -a claude-code`.
  Se o CLI ainda criar `.agents/` + symlinks, trocar o symlink pelo diretório real
  (`cp -rL`) e apagar o `.agents/`. Registrar a fonte em `skills-lock.json`.
- Skills de terceiros ficam fora do gitleaks (`.gitleaks.toml` → `^\.claude/skills/`).
