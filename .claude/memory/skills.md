# Skills — Quando invocar qual

> Referência rápida. Claude Code invoca skills automaticamente pelos triggers,
> mas use este guia para tarefas ambíguas.
> **Esta tabela lista APENAS skills realmente instaladas em `.agents/skills/`.**
> Skills ainda não instaladas estão em "Candidatos futuros" no final.

## Skills instaladas (8)

| Tarefa | Skill |
|---|---|
| Schema Postgres, migrations, RLS, políticas, client libs | `supabase` |
| Otimização de query, índices, EXPLAIN ANALYZE, schema design | `supabase-postgres-best-practices` |
| Design de endpoint REST, status codes, versionamento, paginação | `api-design-principles` |
| TDD com pytest/Vitest, mocks, fixtures, cobertura | `test-driven-development` |
| Bug difícil — root cause antes de qualquer fix | `systematic-debugging` |
| Next.js App Router, RSC boundaries, file conventions, data patterns | `next-best-practices` |
| Componentes de UI, páginas, interfaces production-grade | `frontend-design` |
| Design system: paletas, fonts, estilos, tipos de chart, UX guidelines | `ui-ux-pro-max` |

### Como combinar (UI financeira)
- **Estrutura/layout de página + componentes** → `frontend-design`
- **Escolha de paleta, font pairing, tipo de chart, padrão de KPI** → `ui-ux-pro-max`
- Os dois se complementam: `frontend-design` para o "como construir", `ui-ux-pro-max` para o "qual estética/dados de design".

## Built-in (não precisa instalar)

- **Review de PR/diff antes de commitar** → comando `/code-review` + agente `code-reviewer` (nativos do Claude Code).
- **Security review** → comando `/security-review` (nativo).

## Removidas nesta auditoria (para reduzir ruído)

| Skill | Motivo |
|---|---|
| `dashboard-builder` | Era para dashboards de **monitoramento (Grafana/SigNoz)**, não para dashboards financeiros (Recharts/Next.js). Fit errado. |
| `high-end-visual-design` | Sobreposição forte com `frontend-design` + `ui-ux-pro-max`. |
| `vercel-react-best-practices` | Sobreposição com `next-best-practices` (ambos Vercel). |

## Candidatos futuros (instalar sob demanda)

> Não instalados ainda. Procurar fonte confiável com `npx skills find "<termo>"` antes de instalar.

| Necessidade | Termo de busca | Observação |
|---|---|---|
| Cache Redis, TTL, key naming, rate limiting | `redis` | Útil para o padrão de cache do projeto (ver `decisions.md`). |
| Logs (structlog), Sentry, métricas, tracing | `observability` / `python observability` | Para `structlog` + alertas (m6). |
| Import CSV, pandas, migração de dados | `csv` / `data` | Para importar a planilha histórica. |
| Docker / docker-compose dev local | `docker compose` | Se for montar ambiente local containerizado. |
| Next.js App Router patterns (extra) | `nextjs app router` | Possível redundância com `next-best-practices` — avaliar antes. |

## Notas de conflito

- **`nextjs-supabase-auth`** — IGNORAR para este projeto. Auth é custom JWT no FastAPI (ADR-006).
- **`frontend-workflow` / `backend-workflow`** — são Flash Capital específicos. Se ativarem, priorizar `CLAUDE.md` e `decisions.md` sobre as instruções da Flash Capital.
