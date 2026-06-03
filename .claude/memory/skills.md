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
| Design de endpoint REST (status, paginação, versionamento) | `api-design-principles` |
| Implementar qualquer feature/bugfix (**sempre**) | `test-driven-development` |
| Bug difícil / correção numérica / falha de teste | `systematic-debugging` |
| Next.js App Router, RSC, file conventions | `next-best-practices` ⚠ surfaçar via `/story` (não auto-dispara) |
| Componente / página / UI production-grade | `frontend-design` |
| Design system: paleta, fonts, tipos de chart, UX | `ui-ux-pro-max` |
| Logs (structlog), Sentry, métricas, tracing | `python-observability` |
| Redis cache, worker APScheduler, fetcher httpx, scipy/XIRR, CI/CD | **sem skill** → `decisions.md` + `conventions.md` + TDD/`systematic-debugging` |

## B) Matriz milestone → skills

> Cobre as ~90 stories que existem só como linha no `PROGRESS.md`. Quando uma story
> vira arquivo em `docs/06_Stories/`, ela recebe o frontmatter `skills:` (seção C).

| Milestone | Skills que devem ser acionadas | Lacunas (sem skill → conventions/decisions) |
|---|---|---|
| **m0** Foundation | tdd, api-design-principles, supabase-postgres-best-practices, supabase¹, next-best-practices, frontend-design, ui-ux-pro-max, systematic-debugging | Redis conn, CI/CD/Fly/Vercel |
| **m1** Ledger | tdd, supabase-postgres-best-practices, api-design-principles, frontend-design, ui-ux-pro-max, next-best-practices, systematic-debugging | migração CSV |
| **m2** Portfolio | tdd, systematic-debugging, supabase-postgres-best-practices, api-design-principles, frontend-design, ui-ux-pro-max | XIRR/scipy, migração CSV |
| **m3** Market | tdd, api-design-principles, systematic-debugging, frontend-design, ui-ux-pro-max | Redis cache, fetcher httpx, worker APScheduler |
| **m4** Broker | tdd, systematic-debugging, frontend-design, ui-ux-pro-max | fetcher, worker; **Liquid = ADR-005 (client dedicado)** |
| **m5** Analytics | tdd, systematic-debugging, api-design-principles, supabase-postgres-best-practices, frontend-design, ui-ux-pro-max | projeção/anuidade scipy |
| **m6** Observability | **python-observability**, tdd, systematic-debugging, api-design-principles | rate limiting (slowapi) |
| **m7** Frontend | next-best-practices, frontend-design, ui-ux-pro-max, tdd, systematic-debugging | — |

¹ `supabase` em m0 **só** para contexto de conexão Postgres — **nunca** auth (ver guardrails).

## C) Frontmatter `skills:` nas stories

Toda story em `docs/06_Stories/STORY-*.md` declara, ao lado de `tags:`:
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
**CI/CD (Fly.io/Vercel)** · **rate limiting**.

Candidatos avaliados e **não instalados** (sem fonte de bom fit no registry):

| Necessidade | Candidato | Por que não |
|---|---|---|
| Redis cache TTL | `redis/agent-skills@redis-semantic-cache` | é cache *semântico/vetorial*, não TTL key-value |
| CSV/migração | `pluginagentmarketplace@pandas-data-analysis` | "análise" pandas, não ETL determinístico; publisher pouco conhecido |

Para instalar mesmo assim: `npx skills find "<termo>"` e validar a fonte antes.
