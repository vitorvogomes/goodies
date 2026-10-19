# Skills — Roteamento por story / milestone

> **Fonte autoritativa de roteamento de skills.** O comando `/story` consulta este
> arquivo para anunciar e invocar as skills certas.
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
| Tabelas de dados (ordenar, filtrar, paginar, agrupar) | `tanstack-table` (+ `shadcn` data-table) — **atenção:** o projeto usa `@tanstack/react-table` **v9** (compatível com React Compiler); a skill documenta v8, conferir a API v9 |
| Layout / navegação / hierarquia de informação | `better-layout` |
| Polimento de UI (raios, alinhamento, profundidade, hit areas) | `better-ui` + `emil-design-eng` |
| Acessibilidade (contraste, foco, teclado, ARIA) | `better-accessibility` |
| Microcopy pt-BR (rótulos, estados vazios, erros) | `better-writing` |
| **Revisão de UI antes do `/done`** (story de frontend) | `interface-review` (ou `better-interface` p/ passe completo) |
| App Router avançado (streaming, parallel/intercepting routes p/ drawers) | `nextjs-app-router-patterns` + `next-best-practices` |
| Testes de frontend (componentes, hooks, utils) | `vitest-testing` |
| Procurar skill para uma lacuna | `find-skills` (critério: fonte oficial ou ≥1K installs; auditar antes) |
| Logs (structlog), Sentry, métricas, tracing | `python-observability` |
| Redis cache, worker APScheduler, fetcher httpx, scipy/XIRR | **sem skill** → `decisions.md` + `conventions.md` + TDD/`systematic-debugging` |

## B) Goodies v2 — épico → skills (usado pelo `/story`)

| Épico v2 (`docs/v2/planning/epics.md`) | Skills |
|---|---|
| 1. App novo de pé (docs, backup, versões, visual, 4 áreas, período, login, endurecimento) | tdd, shadcn, tailwind-design-system, next-best-practices, nextjs-app-router-patterns, vitest-testing, better-layout, python-observability (backup/structlog), systematic-debugging |
| 2. Categorias, regras e histórico (common, migrações, `categorize()`, Ajustes) | tdd, supabase-postgres-best-practices, api-design-principles, fastapi, tanstack-table, better-writing |
| 3. Hub de import, revisão e avisos (ingest, adapters, revisão, conferência, desfazer) | tdd, systematic-debugging, supabase-postgres-best-practices, fastapi, tanstack-table, better-interface, better-accessibility |
| 4. Painel principal | ui-ux-pro-max, better-interface, emil-design-eng, nextjs-app-router-patterns, tdd |
| 5. Fechamento e recuperação (closing, snapshot, retroativo, assistente) | tdd, systematic-debugging, supabase-postgres-best-practices, api-design-principles, better-interface |
| 6. Orçamento e custos fixos | tdd, api-design-principles, tanstack-table, better-interface, better-writing |
| 7. Investimentos (posições, XIRR, CDI/IPCA, caixinhas, debêntures, corretora, conciliação) | tdd, systematic-debugging, supabase-postgres-best-practices, python-observability (fetcher BCB), tanstack-table |
| 8. Aporte, objetivos e distribuição | tdd, api-design-principles, tanstack-table, better-interface |
| 9. Histórico e gráficos | dataviz, ui-ux-pro-max, better-interface, tanstack-table, tdd |
| 10. Ajustes completos e fim da v1 | tdd, better-accessibility, interface-review, next-best-practices, systematic-debugging |

Lacunas sem skill (Redis, APScheduler, fetcher httpx, scipy/XIRR): seguir `decisions.md` + `conventions.md` + TDD.

## C) Skills por story

As stories da v2 vivem em `docs/v2/planning/epics.md` (sem arquivo próprio): `/story` usa a tabela B pelo épico.
Trabalho novo fora do backlog (ajuste pedido no dia a dia) escolhe pela tabela A.

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

## G) Instalação de skills (layout do repo)

- Skills vivem **só** em `.claude/skills/<nome>/` (diretórios reais, versionados). A pasta
  `.agents/` foi removida em 2026-10-17 — não recriar.
- Instalar com alvo exclusivo Claude Code: `npx skills add <owner/repo> --skill <nome> -a claude-code`.
  Se o CLI ainda criar `.agents/` + symlinks, trocar o symlink pelo diretório real
  (`cp -rL`) e apagar o `.agents/`. Registrar a fonte em `skills-lock.json`.
- Skills de terceiros ficam fora do gitleaks (`.gitleaks.toml` → `^\.claude/skills/`).
